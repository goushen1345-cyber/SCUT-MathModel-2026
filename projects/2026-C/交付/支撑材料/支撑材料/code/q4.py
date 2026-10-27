from pathlib import Path
import os,json,time,hashlib,csv,itertools
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import joblib
R=Path(__file__).resolve().parents[1]
P=R
O=R/'reproduced'
DATE=pd.Timestamp('2025-01-01')
N=365*144
N_DAYS=365
SLOTS=144
CAP=5000/6
EXEC_COLUMNS=['storage_start','storage_end','received','grid_load','pv_load','grid_charge','pv_charge','discharge','emergency','unused_order','unused_pv','load_energy']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def daystr(d):return str((DATE+pd.Timedelta(days=int(d))).date())
class Budget:
 def __init__(self):self.calls=0;self.lp_calls=0;self.price_fits=0
 def check(self):pass
 def save(self):pass
class Logs:
 def event(self,*a,**kw):pass
budget=Budget();logs=Logs()
class Q2Risk:
    def __init__(self, data):
        self.data = data
        self.errors = {}

    def error(self, day):
        if day not in self.errors:
            load_hat, pv_hat, _ = self.data.history(day, 4, 7)
            load, pv = self.data.truth(day)
            self.errors[day] = ((load - pv) - (load_hat[:SLOTS] - pv_hat[:SLOTS])) / 6
        return self.errors[day]

    def margin(self, day, q=0.7, history_days=28, group_hours=4, decay=0.7):
        indices = list(range(max(1, day - history_days), day))
        pool = np.array([self.error(index) for index in indices])
        result = np.zeros(SLOTS)
        width = group_hours * 6
        records = []
        for start in range(0, SLOTS, width):
            values = (pool[:, start:start + width] if len(indices) >= 14 else pool).ravel()
            if len(indices) < 7:
                raw = 0.0
                count = int(values.size)
            else:
                weights = np.repeat(
                    decay ** np.arange(len(indices) - 1, -1, -1),
                    width if len(indices) >= 14 else SLOTS,
                )
                order = np.argsort(values, kind="stable")
                cdf = np.cumsum(weights[order])
                raw = float(values[order][np.searchsorted(cdf, q * cdf[-1], side="left")])
                count = int(values.size)
            result[start:start + width] = max(0.0, raw)
            records.append({"slot_start": start, "value": max(0.0, raw), "count": count})
        return np.tile(result, 2), records

class PriceFeatures:
    FEATURE_NAMES = [
        "attachment1_base", "matching_weekday_median4", "recent7_median", "lag7_price",
        "predicted_net_load_1000kw", "current_day_level", "current_level_decay6h",
        "last_residual_decay1h", "lead_hours", "season_sin", "season_cos",
        *[f"weekday_{i}" for i in range(7)], "release_fraction",
    ]

    def __init__(self, prices, base, supply, branch):
        self.prices = prices
        self.base = base
        self.supply = supply
        self.branch = branch
        self.releases = [0] if branch == "Q4-2" else [0, 36, 72, 108]
        self._history_cache = {}

    def supply_forecast(self, day, slot):
        if self.branch == "Q4-2":
            target = day * SLOTS + np.arange(288)
            net = self.supply["load"][day] - self.supply["pv"][day]
        else:
            batch = day * 4 + slot // 36
            n = 288 - slot
            target = day * SLOTS + slot + np.arange(n)
            net = self.supply["load"][day, slot:slot + n] - self.supply["pv"][batch, :n]
        return target.astype(int), np.asarray(net, dtype=float)

    def history_curve(self, decision_day, target_day):
        key = (int(decision_day), int(target_day))
        if key in self._history_cache:
            return self._history_cache[key]
        matching = [target_day - 7 * lag for lag in range(1, 5) if 0 <= target_day - 7 * lag < decision_day]
        if matching:
            curve = np.median(self.prices[matching], axis=0)
            source = "matching_weekday"
        else:
            recent = list(range(max(0, decision_day - 7), decision_day))
            curve = np.median(self.prices[recent], axis=0) if recent else self.base.copy()
            source = "recent_or_attachment1"
        self._history_cache[key] = (curve, matching, source)
        return self._history_cache[key]

    def simple(self, day, slot, targets=None):
        if targets is None:
            targets, _ = self.supply_forecast(day, slot)
        slots = targets % SLOTS
        days = targets // SLOTS
        out = np.empty(len(targets))
        for target_day in np.unique(days):
            mask = days == target_day
            curve, _, _ = self.history_curve(day, int(target_day))
            out[mask] = curve[slots[mask]]
        if slot > 0:
            current_curve, _, _ = self.history_curve(day, day)
            level = float(np.median(self.prices[day, :slot] - current_curve[:slot]))
            out[days == day] += level
        return np.maximum(out, 0.001)

    def matrix(self, day, slot, targets, predicted_net):
        target_slots = targets % SLOTS
        target_days = targets // SLOTS
        same = np.empty(len(targets))
        recent = np.empty(len(targets))
        lag7 = np.empty(len(targets))
        for target_day in np.unique(target_days):
            mask = target_days == target_day
            slots = target_slots[mask]
            curve, _, _ = self.history_curve(day, int(target_day))
            same[mask] = curve[slots]
            recent_days = list(range(max(0, day - 7), day))
            recent[mask] = np.median(self.prices[recent_days][:, slots], axis=0) if recent_days else self.base[slots]
            lag_day = int(target_day) - 7
            lag7[mask] = self.prices[lag_day, slots] if 0 <= lag_day < day else curve[slots]

        current_level = 0.0
        last_residual = 0.0
        if slot > 0:
            current_curve, _, _ = self.history_curve(day, day)
            residual = self.prices[day, :slot] - current_curve[:slot]
            current_level = float(np.median(residual))
            last_residual = float(residual[-1])
        lead_hours = (targets - (day * SLOTS + slot)) / 6
        same_day = (target_days == day).astype(float)
        current = current_level * same_day
        current_decay = current_level * np.exp(-lead_hours / 6) * same_day
        last_decay = last_residual * np.exp(-lead_hours) * same_day
        dates = DATE + pd.to_timedelta(target_days, unit="D")
        day_of_year = np.asarray(dates.dayofyear, dtype=float)
        weekday = np.asarray(dates.dayofweek, dtype=int)
        columns = [
            self.base[target_slots], same, recent, lag7, predicted_net / 1000,
            current, current_decay, last_decay, lead_hours,
            np.sin(2 * np.pi * day_of_year / 365), np.cos(2 * np.pi * day_of_year / 365),
        ]
        columns.extend((weekday == index).astype(float) for index in range(7))
        columns.append(np.full(len(targets), slot / 108 if slot else 0.0))
        matrix = np.column_stack(columns)
        assert matrix.shape[1] == len(self.FEATURE_NAMES) and np.isfinite(matrix).all()
        return matrix

class PriceModels:
    def __init__(self, features, branch):
        self.features = features
        self.branch = branch
        self.datasets = {}
        self.models = {}
        self.model_dir = O / "price_models" / branch.replace("-", "_")
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def training(self, cutoff_day):
        if cutoff_day in self.datasets:
            return self.datasets[cutoff_day]
        rows, targets = [], []
        for origin_day in range(max(1, cutoff_day - 56), cutoff_day):
            for release in self.features.releases:
                absolute, net = self.features.supply_forecast(origin_day, release)
                valid = (absolute < cutoff_day * SLOTS) & (absolute < N_DAYS * SLOTS)
                if not valid.any():
                    continue
                rows.append(self.features.matrix(origin_day, release, absolute[valid], net[valid]))
                targets.append(self.features.prices.reshape(-1)[absolute[valid]])
        X = np.vstack(rows)
        y = np.concatenate(targets)
        assert len(y) >= 500 and np.isfinite(X).all() and np.isfinite(y).all()
        self.datasets[cutoff_day] = (X, y)
        return X, y

    def fit(self, candidate, cutoff_day):
        key = (candidate, cutoff_day)
        if key in self.models:
            return self.models[key]
        X, y = self.training(cutoff_day)
        start = time.perf_counter()
        budget.price_fits += 1
        budget.check()
        if candidate == "P2":
            scaler = StandardScaler()
            scaled = scaler.fit_transform(X)
            model = Ridge(alpha=10.0)
            with threadpool_limits(limits=1):
                model.fit(scaled, y)
            original_coef = model.coef_ / scaler.scale_
            record = {
                "coefficients_original": dict(zip(self.features.FEATURE_NAMES, original_coef.astype(float))),
                "intercept_original": float(model.intercept_ - original_coef @ scaler.mean_),
                "alpha": 10.0,
            }
        else:
            scaler = None
            model = HistGradientBoostingRegressor(
                max_leaf_nodes=15, max_iter=100, learning_rate=0.05,
                min_samples_leaf=50, l2_regularization=1.0,
                early_stopping=False, random_state=2026,
            )
            with threadpool_limits(limits=1):
                model.fit(X, y)
            record = {
                "max_leaf_nodes": 15, "iterations": int(model.n_iter_),
                "learning_rate": 0.05, "min_samples_leaf": 50, "random_state": 2026,
            }
        elapsed = time.perf_counter() - start
        path = self.model_dir / f"{candidate}-cutoff-{cutoff_day:03d}.joblib"
        joblib.dump({"model": model, "scaler": scaler, "features": self.features.FEATURE_NAMES}, path, compress=3)
        record.update({
            "branch": self.branch, "candidate": candidate, "cutoff_day": int(cutoff_day),
            "cutoff_datetime": daystr(cutoff_day) + " 00:00", "training_rows": int(len(y)),
            "training_origin_start": daystr(max(1, cutoff_day - 56)),
            "latest_target_end": daystr(cutoff_day) + " 00:00",
            "seconds": elapsed, "model_path": str(path.relative_to(R)), "model_sha256": sha(path),
        })
        logs.event("price_fit_log", record)
        self.models[key] = (model, scaler)
        budget.save()
        return self.models[key]

    def predict(self, candidate, day, slot):
        targets, net = self.features.supply_forecast(day, slot)
        if candidate == "P1" or day < 7:
            result = self.features.simple(day, slot, targets)
            fit_cutoff = None
            fallback = candidate != "P1"
        else:
            cutoff = 7 + ((day - 7) // 7) * 7
            model, scaler = self.fit(candidate, cutoff)
            X = self.features.matrix(day, slot, targets, net)
            with threadpool_limits(limits=1):
                result = model.predict(scaler.transform(X) if scaler is not None else X)
            result = np.maximum(result, 0.001)
            fit_cutoff = cutoff
            fallback = False
        logs.event("price_forecast_log", {
            "branch": self.branch, "candidate": candidate, "decision_day": int(day),
            "decision_date": daystr(day), "release_slot": int(slot),
            "known_price_intervals_today": int(slot), "fit_cutoff_day": fit_cutoff,
            "early_history_fallback": fallback, "forecast_points": int(len(result)),
            "minimum": float(np.min(result)), "maximum": float(np.max(result)),
            "sha256": hashlib.sha256(np.asarray(result, dtype=np.float64).tobytes()).hexdigest(),
        })
        return result

class Q42Planner:
    def __init__(self, terminal_value):
        n = 288
        self.n = n
        self.terminal_value = float(terminal_value)
        eq = lil_matrix((n, 4 * n))
        ub = lil_matrix((n, 4 * n))
        for k in range(n):
            eq[k, k] = -0.9
            eq[k, n + k] = -0.9
            eq[k, 2 * n + k] = 1 / 0.9
            eq[k, 3 * n + k] = 1
            if k:
                eq[k, 3 * n + k - 1] = -1
            ub[k, k] = ub[k, n + k] = 1
        self.eq = eq.tocsr()
        self.ub = ub.tocsr()
        self.bub = np.full(n, CAP)

    def solve(self, load, pv, state, margin, price, meta):
        budget.lp_calls += 1
        budget.check()
        n = self.n
        net = np.maximum((load[:n] - pv[:n]) / 6 + margin[:n], 0)
        excess = np.maximum((pv[:n] - load[:n]) / 6 - margin[:n], 0)
        lower = np.r_[np.zeros(3 * n), np.full(n, 1200.0)]
        upper = np.r_[np.full(n, CAP), np.minimum(excess, CAP), np.minimum(net, CAP), np.full(n, 10800.0)]
        beq = np.zeros(n)
        beq[0] = state
        objective = np.r_[price[:n], np.zeros(n), -price[:n], np.zeros(n)]
        objective[-1] = -self.terminal_value
        start = time.perf_counter()
        result = linprog(
            objective, A_ub=self.ub, b_ub=self.bub, A_eq=self.eq, b_eq=beq,
            bounds=np.column_stack((lower, upper)), method="highs",
            options={"time_limit": 10.0, "primal_feasibility_tolerance": 1e-8, "dual_feasibility_tolerance": 1e-8},
        )
        if not result.success:
            raise RuntimeError(result.message)
        x, y, z, storage = np.split(result.x, 4)
        order = np.maximum(net - z + x, 0)
        residual = max(
            float(np.max(np.abs(self.eq @ result.x - beq))),
            float(np.max(self.ub @ result.x - self.bub)),
            float(np.max(lower - result.x)), float(np.max(result.x - upper)),
        )
        finite = np.isfinite(upper)
        dual = (beq @ result.eqlin.marginals + self.bub @ result.ineqlin.marginals
                + lower @ result.lower.marginals + upper[finite] @ result.upper.marginals[finite])
        gap = abs(result.fun - dual)
        simultaneous = int(np.sum((x + y > 1e-6) & (z > 1e-6)))
        assert residual < 1e-6 and gap < 1e-4 and simultaneous == 0
        logs.event("solver_checks", dict(meta, residual=residual, dual_gap=float(gap),
                                         simultaneous=simultaneous, status=int(result.status),
                                         seconds=time.perf_counter() - start))
        return order

class Q43Planner:
    def __init__(self, terminal_value):
        self.terminal_value = float(terminal_value)
        self.cache = {}

    def matrices(self, n, fixed_count):
        key = (n, fixed_count)
        if key in self.cache:
            return self.cache[key]
        eq = lil_matrix((2 * n, 8 * n))
        ub = lil_matrix((2 * n + 2 * fixed_count, 8 * n))
        for i in range(n):
            eq[i, i] = -0.9
            eq[i, n + i] = -0.9
            eq[i, 2 * n + i] = 1 / 0.9
            eq[i, 3 * n + i] = 1
            if i:
                eq[i, 3 * n + i - 1] = -1
            eq[n + i, 6 * n + i] = 1
            eq[n + i, i] = -1
            eq[n + i, 2 * n + i] = 1
            eq[n + i, 4 * n + i] = 1
            eq[n + i, 5 * n + i] = -1
            ub[i, i] = ub[i, n + i] = 1
            ub[n + i, 2 * n + i] = ub[n + i, 4 * n + i] = 1
        for i in range(fixed_count):
            ub[2 * n + i, 6 * n + i] = 1
            ub[2 * n + i, 7 * n + i] = -1
            ub[2 * n + fixed_count + i, 6 * n + i] = -1
            ub[2 * n + fixed_count + i, 7 * n + i] = -1
        self.cache[key] = eq.tocsr(), ub.tocsr()
        return self.cache[key]

    def solve(self, load, pv, state, margin, slot, q0, price, meta):
        budget.lp_calls += 1
        budget.check()
        n = len(load)
        fixed_count = 0 if q0 is None else min(SLOTS - slot, n)
        eq, ub = self.matrices(n, fixed_count)
        net = np.maximum((load - pv) / 6 + margin, 0)
        surplus = np.maximum(-((load - pv) / 6 + margin), 0)
        objective = np.zeros(8 * n)
        objective[4 * n:5 * n] = 5 * price
        objective[6 * n:7 * n] = price
        objective[7 * n:7 * n + fixed_count] = 0.5 * price[:fixed_count]
        objective[4 * n - 1] = -self.terminal_value
        lower = np.zeros(8 * n)
        upper = np.full(8 * n, np.inf)
        upper[:n] = CAP
        upper[n:2 * n] = np.minimum(surplus, CAP)
        upper[2 * n:3 * n] = CAP
        lower[3 * n:4 * n] = 1200
        upper[3 * n:4 * n] = 10800
        upper[7 * n + fixed_count:] = 0
        beq = np.r_[np.zeros(n), net]
        beq[0] = state
        bub = np.r_[np.full(n, CAP), net,
                    ([] if fixed_count == 0 else q0[:fixed_count]),
                    ([] if fixed_count == 0 else -q0[:fixed_count])]
        start = time.perf_counter()
        result = linprog(
            objective, A_ub=ub, b_ub=bub, A_eq=eq, b_eq=beq,
            bounds=np.column_stack((lower, upper)), method="highs",
            options={"time_limit": 10.0, "primal_feasibility_tolerance": 1e-8, "dual_feasibility_tolerance": 1e-8},
        )
        if not result.success:
            raise RuntimeError(result.message)
        z = result.x.reshape(8, n)
        residual = max(
            float(np.max(np.abs(eq @ result.x - beq))), float(np.max(ub @ result.x - bub)),
            float(np.max(lower - result.x)), float(np.max(result.x - upper)),
        )
        finite = np.isfinite(upper)
        dual = (beq @ result.eqlin.marginals + bub @ result.ineqlin.marginals
                + lower @ result.lower.marginals + upper[finite] @ result.upper.marginals[finite])
        gap = abs(result.fun - dual)
        simultaneous = int(np.sum((z[0] + z[1] > 1e-6) & (z[2] > 1e-6)))
        assert residual < 1e-6 and gap < 1e-4 and simultaneous == 0
        logs.event("solver_checks", dict(meta, residual=residual, dual_gap=float(gap),
                                         simultaneous=simultaneous, status=int(result.status),
                                         seconds=time.perf_counter() - start))
        return np.maximum(z[6], 0)

def execute_block(load_kw, pv_kw, order, initial):
    output = np.empty((len(order), len(EXEC_COLUMNS)))
    state = float(initial)
    for k in range(len(order)):
        load = float(load_kw[k] / 6)
        pv = float(pv_kw[k] / 6)
        paid = max(0.0, float(order[k]))
        direct = min(load, pv)
        need = load - direct
        surplus = pv - direct
        start = state
        if need > paid:
            discharge = min(need - paid, CAP, max(0.0, 0.9 * (state - 1200)))
            emergency = max(0.0, need - paid - discharge)
            grid_charge = pv_charge = 0.0
            received = paid
        else:
            charge = min(surplus + paid - need, CAP, max(0.0, (10800 - state) / 0.9))
            pv_charge = min(surplus, charge)
            grid_charge = charge - pv_charge
            received = need + grid_charge
            discharge = emergency = 0.0
        state += 0.9 * (grid_charge + pv_charge) - discharge / 0.9
        output[k] = [
            start, state, received, received - grid_charge, direct, grid_charge, pv_charge,
            discharge, emergency, max(0.0, paid - received), max(0.0, surplus - pv_charge), load,
        ]
        assert 1200 - 1e-6 <= state <= 10800 + 1e-6
        assert abs(received - grid_charge + direct + discharge + emergency - load) < 1e-6
    return output, state
