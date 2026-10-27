"""Causal price candidates P1--P3 with the existing Q2/Q3 supply and storage models."""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import time
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ["NUMEXPR_MAX_THREADS"] = "1"

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

R = Path(__file__).resolve().parent
P = R.parents[3]
O = R / "outputs"
DATE = pd.Timestamp("2025-01-01")
N_DAYS = 365
SLOTS = 144
CAP = 5000 / 6
OFFICIAL_START = 31


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def daystr(day):
    return str((DATE + pd.Timedelta(days=int(day))).date())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Budget:
    def __init__(self):
        self.start = time.perf_counter()
        self.lp_calls = 0
        self.price_fits = 0

    def check(self):
        assert self.lp_calls <= 6200, "LP budget exceeded"
        assert self.price_fits <= 240, "price fit budget exceeded"
        assert time.perf_counter() - self.start <= 1800, "research time budget exceeded"

    def save(self):
        dump(O / "budget.json", {
            "lp_calls": self.lp_calls,
            "price_model_fits": self.price_fits,
            "elapsed_seconds": time.perf_counter() - self.start,
            "limits": {"lp_calls": 6200, "price_model_fits": 240, "seconds": 1800},
        })


class Logs:
    def __init__(self):
        self.handles = {}

    def event(self, name, row):
        if name not in self.handles:
            self.handles[name] = (O / f"{name}.jsonl").open("w", encoding="utf-8")
        self.handles[name].write(json.dumps(row, ensure_ascii=False) + "\n")
        self.handles[name].flush()

    def close(self):
        for handle in self.handles.values():
            handle.close()


budget = Budget()
logs = Logs()


def verify_protocol_sources():
    protocol = json.loads((R / "protocol.json").read_text(encoding="utf-8"))
    checked = {}
    for rel, expected in protocol["source_sha256"].items():
        actual = sha(P / rel)
        assert actual == expected, (rel, expected, actual)
        checked[rel] = actual
    dump(O / "source_hashes.json", checked)


def load_prices_and_base():
    frame = pd.read_csv(P / "data/prepared-v1/actual_price.csv", float_precision="round_trip")
    frame["day"] = (pd.to_datetime(frame.source_date) - DATE).dt.days
    frame["slot"] = (frame.source_minute.astype(int) % 1440) // 10
    assert len(frame) == N_DAYS * SLOTS
    assert not frame.duplicated(["day", "slot"]).any()
    prices = frame.pivot(index="day", columns="slot", values="price_yuan_per_kwh").reindex(
        index=range(N_DAYS), columns=range(SLOTS)
    ).to_numpy()
    assert np.isfinite(prices).all() and np.min(prices) > 0
    ref = pd.read_csv(P / "data/prepared-v1/day_reference.csv", float_precision="round_trip")
    ref["slot"] = (ref.source_minute.astype(int) % 1440) // 10
    ref = ref.sort_values("slot")
    assert list(ref.slot) == list(range(SLOTS))
    return prices, ref.price_yuan_per_kwh.to_numpy(), ref[["load_kw", "pv_forecast_kw"]].to_numpy()


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


def prepare_supply(reference):
    q2_path = P / "questions/Q2/runs/20260911-annual-validation-v1"
    q2 = load_module("q4_q2core", q2_path / "core.py")
    q2_dir = O / "q2_supply_build"
    q2_dir.mkdir()
    q2_data = q2.Data(q2_dir)
    q2_risk = Q2Risk(q2_data)
    q2_load = np.empty((N_DAYS, 288))
    q2_pv = np.empty((N_DAYS, 288))
    q2_margin = np.empty((N_DAYS, 288))
    q2_actual = np.empty((N_DAYS, SLOTS, 2))
    for day in range(N_DAYS):
        if day == 0:
            q2_load[day] = np.tile(reference[:, 0], 2)
            q2_pv[day] = np.tile(reference[:, 1], 2)
            q2_margin[day] = 0
            load, pv = q2_data.truth(day, initialization=True)
        else:
            load_hat, pv_hat, _ = q2_data.history(day, 4, 7)
            q2_load[day] = load_hat
            q2_pv[day] = pv_hat
            q2_margin[day], _ = q2_risk.margin(day)
            load, pv = q2_data.truth(day)
        q2_actual[day, :, 0] = load
        q2_actual[day, :, 1] = pv

    q3_base = P / "questions/Q3/runs/20260911-four-candidates-v1/outputs"
    q3_src = dict(np.load(q3_base / "sources.npz"))
    q3_fc = dict(np.load(q3_base / "forecasts.npz"))
    q3_margin = np.load(
        P / "questions/Q3/runs/20260911-parameter-interpretability-v1/outputs/margins/q60_b070_w28_h03.npz"
    )["values"]
    q3_actual = q3_src["actual"].copy()
    assert q3_actual.shape == (N_DAYS * SLOTS + 1, 2)
    q3_actual[0] = reference[0]
    assert np.isfinite(q3_actual[:-1]).all()
    np.savez_compressed(
        O / "supply_inputs.npz",
        q2_load=q2_load,
        q2_pv=q2_pv,
        q2_margin=q2_margin,
        q2_actual=q2_actual,
        q3_load=q3_fc["L"],
        q3_pv=q3_fc["fused"],
        q3_margin=q3_margin,
        q3_actual=q3_actual,
    )
    return {
        "Q4-2": {"load": q2_load, "pv": q2_pv, "margin": q2_margin, "actual": q2_actual},
        "Q4-3": {"load": q3_fc["L"], "pv": q3_fc["fused"], "margin": q3_margin, "actual": q3_actual},
    }


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
        self.model_dir.mkdir(parents=True)

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


def build_price_forecasts(prices, base, supplies):
    candidates = ["P1", "P2", "P3"]
    q42 = np.full((3, N_DAYS, 288), np.nan)
    q43 = np.full((3, N_DAYS * 4, 288), np.nan)
    for branch, target in (("Q4-2", q42), ("Q4-3", q43)):
        features = PriceFeatures(prices, base, supplies[branch], branch)
        models = PriceModels(features, branch)
        for ci, candidate in enumerate(candidates):
            for day in range(N_DAYS):
                for slot in features.releases:
                    values = models.predict(candidate, day, slot)
                    if branch == "Q4-2":
                        target[ci, day, :len(values)] = values
                    else:
                        target[ci, day * 4 + slot // 36, :len(values)] = values
                if (day + 1) % 50 == 0:
                    print(json.dumps({"event": "price_progress", "branch": branch, "candidate": candidate,
                                      "days": day + 1, "fits": budget.price_fits}, ensure_ascii=False), flush=True)
    np.savez_compressed(O / "price_forecasts.npz", q42=q42, q43=q43, candidates=np.array(candidates))
    return candidates, q42, q43


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


EXEC_COLUMNS = ["storage_start", "storage_end", "received", "grid_load", "pv_load", "grid_charge",
                "pv_charge", "discharge", "emergency", "unused_order", "unused_pv", "load_energy"]


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


def save_daily(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig", float_format="%.17g")


def official_summary(frame, branch, candidate, price_metrics, start_state, end_state):
    official = frame[frame.day >= OFFICIAL_START]
    result = {
        "branch": branch, "candidate": candidate, "days": int(len(official)),
        "ordinary_cost": float(official.ordinary_cost.sum()),
        "adjustment_cost": float(official.adjustment_cost.sum()),
        "ordinary_settlement_cost": float(official.ordinary_settlement_cost.sum()),
        "emergency_cost": float(official.emergency_cost.sum()),
        "total_cost": float(official.total_cost.sum()),
        "order_kwh": float(official.order_kwh.sum()),
        "emergency_kwh": float(official.emergency_kwh.sum()),
        "unused_order_kwh": float(official.unused_order_kwh.sum()),
        "unused_pv_kwh": float(official.unused_pv_kwh.sum()),
        "emergency_days": int((official.emergency_kwh > 1e-6).sum()),
        "official_start_kwh": float(official.initial.iloc[0]),
        "official_end_kwh": float(official.final.iloc[-1]),
        "jan1_start_kwh": 6000.0, "jan31_end_kwh": float(start_state),
        **price_metrics,
    }
    return result


def evaluate_prices(prices, forecast, branch):
    actuals, predictions = [], []
    if branch == "Q4-2":
        for day in range(OFFICIAL_START, N_DAYS):
            actuals.append(prices[day])
            predictions.append(forecast[day, :SLOTS])
    else:
        for day in range(OFFICIAL_START, N_DAYS):
            for release in range(4):
                actuals.append(prices[day, release * 36:(release + 1) * 36])
                predictions.append(forecast[day * 4 + release, :36])
    actual = np.concatenate(actuals)
    predicted = np.concatenate(predictions)
    error = np.abs(actual - predicted)
    threshold = float(prices[OFFICIAL_START:].reshape(-1).quantile(.95)) if hasattr(prices, "quantile") else float(np.quantile(prices[OFFICIAL_START:], .95))
    high = actual >= threshold
    evening_slots = np.tile(np.arange(SLOTS), N_DAYS - OFFICIAL_START)
    evening = (evening_slots >= 19 * 6) & (evening_slots < 22 * 6)
    return {
        "price_mae": float(error.mean()), "price_rmse": float(np.sqrt(np.mean((actual - predicted) ** 2))),
        "top5_price_mae": float(error[high].mean()), "evening_price_mae": float(error[evening].mean()),
        "price_bias": float(np.mean(predicted - actual)), "top5_threshold": threshold,
    }


def simulate_q42(candidates, forecasts, prices, base, supply, q1_order):
    planner = Q42Planner(terminal_value=0.9 * base[0])
    results = []
    strategies = O / "strategies"
    strategies.mkdir(exist_ok=True)
    for ci, candidate in enumerate(candidates):
        state = 6000.0
        orders = np.empty((N_DAYS, SLOTS))
        execution = np.empty((N_DAYS, SLOTS, len(EXEC_COLUMNS)))
        daily = []
        for day in range(N_DAYS):
            initial = state
            if day == 0:
                order = q1_order.copy()
            else:
                order = planner.solve(
                    supply["load"][day], supply["pv"][day], state, supply["margin"][day], forecasts[ci, day],
                    {"branch": "Q4-2", "candidate": candidate, "day": day, "release_slot": 0},
                )[:SLOTS]
            block, state = execute_block(supply["actual"][day, :, 0], supply["actual"][day, :, 1], order, state)
            orders[day] = order
            execution[day] = block
            ordinary = float(prices[day] @ order)
            emergency = float(5 * prices[day] @ block[:, 8])
            daily.append({
                "branch": "Q4-2", "candidate": candidate, "day": day, "date": daystr(day),
                "initial": initial, "final": state, "ordinary_cost": ordinary, "adjustment_cost": 0.0,
                "ordinary_settlement_cost": ordinary, "emergency_cost": emergency, "total_cost": ordinary + emergency,
                "order_kwh": float(order.sum()), "emergency_kwh": float(block[:, 8].sum()),
                "unused_order_kwh": float(block[:, 9].sum()), "unused_pv_kwh": float(block[:, 10].sum()),
            })
        frame = pd.DataFrame(daily)
        save_daily(strategies / f"Q4-2-{candidate}.daily.csv", daily)
        np.savez_compressed(strategies / f"Q4-2-{candidate}.npz", order=orders, execution=execution)
        price_metrics = evaluate_prices(prices, forecasts[ci], "Q4-2")
        results.append(official_summary(frame, "Q4-2", candidate, price_metrics,
                                        frame.loc[frame.day == 30, "final"].iloc[0], state))
        print(json.dumps({"event": "strategy_complete", "branch": "Q4-2", "candidate": candidate,
                          "cost": results[-1]["total_cost"], "lp_calls": budget.lp_calls}, ensure_ascii=False), flush=True)
        budget.save()
    return results


def simulate_q43(candidates, forecasts, prices, base, supply, q1_order):
    planner = Q43Planner(terminal_value=0.9 * base[0])
    results = []
    strategies = O / "strategies"
    for ci, candidate in enumerate(candidates):
        state = 6000.0
        qzero = np.empty((N_DAYS, SLOTS))
        versions = np.empty((N_DAYS, 4, SLOTS))
        execution = np.empty((N_DAYS, SLOTS, len(EXEC_COLUMNS)))
        daily = []
        for day in range(N_DAYS):
            initial = state
            order = np.zeros(SLOTS)
            for release_index, slot in enumerate((0, 36, 72, 108)):
                batch = day * 4 + release_index
                if day == 0 and slot == 0:
                    order = q1_order.copy()
                    qzero[day] = order
                else:
                    n = 288 - slot
                    planned = planner.solve(
                        supply["load"][day, slot:slot + n], supply["pv"][batch, :n], state,
                        supply["margin"][batch, :n], slot, None if slot == 0 else qzero[day, slot:],
                        forecasts[ci, batch, :n],
                        {"branch": "Q4-3", "candidate": candidate, "day": day, "release_slot": slot},
                    )
                    order[slot:] = planned[:SLOTS - slot]
                    if slot == 0:
                        qzero[day] = order.copy()
                versions[day, release_index] = order
                truth = supply["actual"][day * SLOTS + slot:day * SLOTS + slot + 36]
                block, state = execute_block(truth[:, 0], truth[:, 1], order[slot:slot + 36], state)
                execution[day, slot:slot + 36] = block
            final_order = order
            delta = final_order - qzero[day]
            original_cost = float(prices[day] @ qzero[day])
            final_energy_cost = float(prices[day] @ final_order)
            adjustment = float(0.5 * prices[day] @ np.abs(delta))
            ordinary_settlement = final_energy_cost + adjustment
            emergency = float(5 * prices[day] @ execution[day, :, 8])
            daily.append({
                "branch": "Q4-3", "candidate": candidate, "day": day, "date": daystr(day),
                "initial": initial, "final": state, "ordinary_cost": final_energy_cost,
                "adjustment_cost": adjustment, "ordinary_settlement_cost": ordinary_settlement,
                "original_plan_cost": original_cost, "emergency_cost": emergency,
                "total_cost": ordinary_settlement + emergency, "order_kwh": float(final_order.sum()),
                "emergency_kwh": float(execution[day, :, 8].sum()),
                "unused_order_kwh": float(execution[day, :, 9].sum()),
                "unused_pv_kwh": float(execution[day, :, 10].sum()),
                "reduced_kwh": float(np.maximum(-delta, 0).sum()), "increased_kwh": float(np.maximum(delta, 0).sum()),
            })
        frame = pd.DataFrame(daily)
        save_daily(strategies / f"Q4-3-{candidate}.daily.csv", daily)
        np.savez_compressed(strategies / f"Q4-3-{candidate}.npz", q0=qzero, versions=versions, execution=execution)
        price_metrics = evaluate_prices(prices, forecasts[ci], "Q4-3")
        results.append(official_summary(frame, "Q4-3", candidate, price_metrics,
                                        frame.loc[frame.day == 30, "final"].iloc[0], state))
        print(json.dumps({"event": "strategy_complete", "branch": "Q4-3", "candidate": candidate,
                          "cost": results[-1]["total_cost"], "lp_calls": budget.lp_calls}, ensure_ascii=False), flush=True)
        budget.save()
    return results


def summarize(results):
    frame = pd.DataFrame(results).sort_values(["branch", "total_cost"])
    frame.to_csv(O / "comparison.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    daily = pd.concat([
        pd.read_csv(O / "strategies" / f"{branch}-{candidate}.daily.csv", float_precision="round_trip")
        for branch in ("Q4-2", "Q4-3") for candidate in ("P1", "P2", "P3")
    ], ignore_index=True)
    official = daily[daily.day >= OFFICIAL_START].copy()
    official["month"] = pd.to_datetime(official.date).dt.month
    monthly = official.groupby(["branch", "candidate", "month"], as_index=False).agg(
        total_cost=("total_cost", "sum"), ordinary_settlement_cost=("ordinary_settlement_cost", "sum"),
        emergency_cost=("emergency_cost", "sum"), emergency_kwh=("emergency_kwh", "sum"),
    )
    monthly.to_csv(O / "monthly.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    winners = {branch: frame[frame.branch == branch].iloc[0].to_dict() for branch in ("Q4-2", "Q4-3")}
    paired = []
    for branch in ("Q4-2", "Q4-3"):
        pivot = official[official.branch == branch].pivot(index="date", columns="candidate", values="total_cost")
        for candidate in ("P2", "P3"):
            diff = pivot["P1"] - pivot[candidate]
            paired.append({
                "branch": branch, "candidate": candidate, "saving_vs_P1": float(diff.sum()),
                "cheaper_days": int((diff > 1e-6).sum()), "dearer_days": int((diff < -1e-6).sum()),
                "same_days": int((np.abs(diff) <= 1e-6).sum()),
                "best_day": str(diff.idxmax()), "best_day_saving": float(diff.max()),
                "worst_day": str(diff.idxmin()), "worst_day_saving": float(diff.min()),
            })
    pd.DataFrame(paired).to_csv(O / "paired_days_summary.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    result = {
        "status": "completed_pending_independent_verification",
        "official_period": {"start": "2025-02-01", "end": "2025-12-31", "days": 334},
        "candidates": results, "winners_by_branch": winners, "paired_vs_P1": paired,
        "selection_boundary": "2025 official period compares candidate families; it is not an untouched cross-year test",
        "budget": json.loads((O / "budget.json").read_text()),
        "protocol_sha256": sha(R / "protocol.json"), "code_sha256": sha(__file__),
    }
    dump(O / "summary.json", result)
    return result


def main():
    if O.exists():
        raise FileExistsError(f"Refusing to overwrite existing run output: {O}")
    O.mkdir()
    verify_protocol_sources()
    prices, base, reference = load_prices_and_base()
    supplies = prepare_supply(reference)
    q1 = pd.read_csv(
        P / "questions/Q1/runs/20260911-compare-v1/outputs/schedules/C04.csv", float_precision="round_trip"
    ).sort_values("start_minute")
    assert list(q1.start_minute) == list(range(0, 1440, 10))
    q1_order = q1.purchase_kwh.to_numpy()
    candidates, q42_prices, q43_prices = build_price_forecasts(prices, base, supplies)
    q42_results = simulate_q42(candidates, q42_prices, prices, base, supplies["Q4-2"], q1_order)
    q43_results = simulate_q43(candidates, q43_prices, prices, base, supplies["Q4-3"], q1_order)
    budget.save()
    result = summarize(q42_results + q43_results)
    dump(O / "environment.json", {
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__, "sklearn": sklearn.__version__, "threads": 1,
    })
    print(json.dumps({"event": "complete", "winners": {k: v["candidate"] for k, v in result["winners_by_branch"].items()},
                      "lp_calls": budget.lp_calls, "price_fits": budget.price_fits}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    finally:
        budget.save()
        logs.close()
