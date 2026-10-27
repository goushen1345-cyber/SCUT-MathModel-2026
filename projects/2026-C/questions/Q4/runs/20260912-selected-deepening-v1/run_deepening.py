"""Execute the approved Q4 selected-model deepening and validation variants."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["NUMEXPR_MAX_THREADS"] = "1"

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits


R = Path(__file__).resolve().parent
P = R.parents[3]
OLD = R.parent / "20260912-three-candidates-v1"
O = R / "outputs"
START = 31
COMMON = 8592.693560925925
RELEASES = (0, 36, 72, 108)

spec = importlib.util.spec_from_file_location("q4base", OLD / "run_compare.py")
q4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q4)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


class RunBudget:
    def __init__(self):
        self.start = time.perf_counter()
        self.lp_calls = 0
        self.price_fits = 0

    def check(self):
        assert self.lp_calls <= 18000, "LP budget exceeded"
        assert self.price_fits <= 600, "price fit budget exceeded"
        assert time.perf_counter() - self.start <= 1800, "time budget exceeded"

    def save(self):
        dump(O / "budget.json", {
            "lp_calls": self.lp_calls,
            "price_model_fits": self.price_fits,
            "elapsed_seconds": time.perf_counter() - self.start,
            "limits": {"lp_calls": 18000, "price_model_fits": 600, "seconds": 1800},
        })


class RunLogs:
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


budget = RunBudget()
logs = RunLogs()
q4.budget = budget
q4.logs = logs


def verify_sources():
    protocol = json.loads((R / "protocol.json").read_text(encoding="utf-8"))
    checked = {}
    for rel, expected in protocol["source_sha256"].items():
        actual = sha(P / rel)
        assert actual == expected, (rel, expected, actual)
        checked[rel] = actual
    dump(O / "source_hashes.json", checked)


class ForecastEngine:
    """Rolling P3 direct-price or P2 residual-price model."""

    def __init__(self, name, features, model_kind, window=56, alpha=10.0,
                 feature_mode="full", max_leaf_nodes=15):
        self.name = name
        self.f = features
        self.model_kind = model_kind
        self.window = int(window)
        self.alpha = float(alpha)
        self.feature_mode = feature_mode
        self.max_leaf_nodes = int(max_leaf_nodes)
        self.cache = {}
        self.model_dir = O / "price_models" / name
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.index = {name: i for i, name in enumerate(self.f.FEATURE_NAMES)}
        if model_kind == "p3":
            if feature_mode == "full":
                self.feature_names = list(self.f.FEATURE_NAMES)
            elif feature_mode == "no_net":
                self.feature_names = [x for x in self.f.FEATURE_NAMES if x != "predicted_net_load_1000kw"]
            elif feature_mode == "history_only":
                self.feature_names = list(self.f.FEATURE_NAMES[:4])
            else:
                raise ValueError(feature_mode)
        else:
            self.feature_names = [
                "matching_weekday_level", "recent_minus_matching", "lag7_minus_matching",
                "attachment1_minus_matching", "predicted_net_load_1000kw",
                "current_day_level", "current_level_decay6h", "last_residual_decay1h",
                "lead_hours", "season_sin", "season_cos",
                *[f"weekday_{i}" for i in range(7)], "release_fraction",
            ]
            if feature_mode == "residual_no_net":
                self.feature_names.remove("predicted_net_load_1000kw")

    def transform(self, full):
        if self.model_kind == "p3":
            return full[:, [self.index[x] for x in self.feature_names]], full[:, self.index["matching_weekday_median4"]]
        match = full[:, self.index["matching_weekday_median4"]]
        cols = {
            "matching_weekday_level": match,
            "recent_minus_matching": full[:, self.index["recent7_median"]] - match,
            "lag7_minus_matching": full[:, self.index["lag7_price"]] - match,
            "attachment1_minus_matching": full[:, self.index["attachment1_base"]] - match,
        }
        for name in (
            "predicted_net_load_1000kw", "current_day_level", "current_level_decay6h",
            "last_residual_decay1h", "lead_hours", "season_sin", "season_cos",
            *[f"weekday_{i}" for i in range(7)], "release_fraction",
        ):
            cols[name] = full[:, self.index[name]]
        return np.column_stack([cols[x] for x in self.feature_names]), match

    def training(self, cutoff):
        xs, ys = [], []
        for origin in range(max(1, cutoff - self.window), cutoff):
            for release in self.f.releases:
                targets, net = self.f.supply_forecast(origin, release)
                valid = (targets < cutoff * q4.SLOTS) & (targets < q4.N_DAYS * q4.SLOTS)
                if not valid.any():
                    continue
                full = self.f.matrix(origin, release, targets[valid], net[valid])
                x, match = self.transform(full)
                y = self.f.prices.reshape(-1)[targets[valid]]
                xs.append(x)
                ys.append(y if self.model_kind == "p3" else y - match)
        x = np.vstack(xs)
        y = np.concatenate(ys)
        assert len(y) >= 500 and np.isfinite(x).all() and np.isfinite(y).all()
        return x, y

    def fit(self, cutoff):
        if cutoff in self.cache:
            return self.cache[cutoff]
        x, y = self.training(cutoff)
        budget.price_fits += 1
        budget.check()
        started = time.perf_counter()
        if self.model_kind == "p3":
            scaler = None
            model = HistGradientBoostingRegressor(
                max_leaf_nodes=self.max_leaf_nodes, max_iter=100, learning_rate=0.05,
                min_samples_leaf=50, l2_regularization=1.0,
                early_stopping=False, random_state=2026,
            )
            with threadpool_limits(limits=1):
                model.fit(x, y)
            detail = {"max_leaf_nodes": self.max_leaf_nodes, "iterations": int(model.n_iter_),
                      "learning_rate": 0.05, "min_samples_leaf": 50}
        else:
            scaler = StandardScaler()
            z = scaler.fit_transform(x)
            model = Ridge(alpha=self.alpha)
            with threadpool_limits(limits=1):
                model.fit(z, y)
            original = model.coef_ / scaler.scale_
            detail = {
                "alpha": self.alpha,
                "coefficients_original": dict(zip(self.feature_names, original.astype(float))),
                "intercept_original": float(model.intercept_ - original @ scaler.mean_),
            }
        path = self.model_dir / f"cutoff-{cutoff:03d}.joblib"
        joblib.dump({"model": model, "scaler": scaler, "features": self.feature_names,
                     "model_kind": self.model_kind, "feature_mode": self.feature_mode}, path, compress=3)
        record = {
            "strategy": self.name, "branch": self.f.branch, "model_kind": self.model_kind,
            "feature_mode": self.feature_mode, "window": self.window, "cutoff_day": int(cutoff),
            "cutoff_datetime": q4.daystr(cutoff) + " 00:00", "latest_target_end": q4.daystr(cutoff) + " 00:00",
            "training_rows": int(len(y)), "feature_names": self.feature_names,
            "model_path": str(path.relative_to(R)), "model_sha256": sha(path),
            "seconds": time.perf_counter() - started, **detail,
        }
        logs.event("price_fit_log", record)
        self.cache[cutoff] = model, scaler
        budget.save()
        return self.cache[cutoff]

    def predict(self, day, release):
        targets, net = self.f.supply_forecast(day, release)
        cutoff = 7 + ((day - 7) // 7) * 7
        model, scaler = self.fit(cutoff)
        full = self.f.matrix(day, release, targets, net)
        x, match = self.transform(full)
        pred = model.predict(x if scaler is None else scaler.transform(x))
        if self.model_kind != "p3":
            pred = match + pred
        pred = np.maximum(pred, 0.001)
        logs.event("price_forecast_log", {
            "strategy": self.name, "branch": self.f.branch, "decision_day": int(day),
            "decision_date": q4.daystr(day), "release_slot": int(release),
            "known_price_intervals_today": int(release), "fit_cutoff_day": int(cutoff),
            "forecast_points": int(len(pred)),
            "sha256": hashlib.sha256(np.asarray(pred, dtype=np.float64).tobytes()).hexdigest(),
        })
        return pred


def build_forecast(engine):
    if engine.f.branch == "Q4-2":
        output = np.full((q4.N_DAYS, 288), np.nan)
        for day in range(START, q4.N_DAYS):
            output[day] = engine.predict(day, 0)
    else:
        output = np.full((q4.N_DAYS * 4, 288), np.nan)
        for day in range(START, q4.N_DAYS):
            for ri, release in enumerate(RELEASES):
                pred = engine.predict(day, release)
                output[day * 4 + ri, :len(pred)] = pred
    np.savez_compressed(O / "price_forecasts" / f"{engine.name}.npz", values=output)
    print(json.dumps({"event": "forecast_complete", "strategy": engine.name,
                      "fits": budget.price_fits}, ensure_ascii=False), flush=True)
    return output


def metrics(prices, forecast, branch):
    return q4.evaluate_prices(prices, forecast, branch)


def summarize(frame, branch, strategy, price_metrics, executable=True):
    return {
        "branch": branch, "strategy": strategy, "days": int(len(frame)),
        "executable": bool(executable),
        "ordinary_cost": float(frame.ordinary_cost.sum()),
        "adjustment_cost": float(frame.adjustment_cost.sum()),
        "ordinary_settlement_cost": float(frame.ordinary_settlement_cost.sum()),
        "emergency_cost": float(frame.emergency_cost.sum()),
        "total_cost": float(frame.total_cost.sum()),
        "order_kwh": float(frame.order_kwh.sum()),
        "emergency_kwh": float(frame.emergency_kwh.sum()),
        "unused_order_kwh": float(frame.unused_order_kwh.sum()),
        "unused_pv_kwh": float(frame.unused_pv_kwh.sum()),
        "emergency_days": int((frame.emergency_kwh > 1e-6).sum()),
        "initial_kwh": COMMON, "final_kwh": float(frame.final.iloc[-1]),
        **price_metrics,
    }


def run_q42(strategy, forecast, prices, base, source, executable=True):
    planner = q4.Q42Planner(terminal_value=0.9 * base[0])
    state = COMMON
    orders = np.empty((334, 144))
    execution = np.empty((334, 144, len(q4.EXEC_COLUMNS)))
    rows = []
    for index, day in enumerate(range(START, q4.N_DAYS)):
        initial = state
        order = planner.solve(source["q2_load"][day], source["q2_pv"][day], state,
                              source["q2_margin"][day], forecast[day],
                              {"branch": "Q4-2", "strategy": strategy, "day": day, "release_slot": 0})[:144]
        block, state = q4.execute_block(source["q2_actual"][day, :, 0], source["q2_actual"][day, :, 1], order, state)
        ordinary = float(prices[day] @ order)
        emergency = float(5 * prices[day] @ block[:, 8])
        rows.append({"branch": "Q4-2", "strategy": strategy, "day": day, "date": q4.daystr(day),
                     "initial": initial, "final": state, "ordinary_cost": ordinary,
                     "adjustment_cost": 0.0, "ordinary_settlement_cost": ordinary,
                     "emergency_cost": emergency, "total_cost": ordinary + emergency,
                     "order_kwh": float(order.sum()), "emergency_kwh": float(block[:, 8].sum()),
                     "unused_order_kwh": float(block[:, 9].sum()), "unused_pv_kwh": float(block[:, 10].sum())})
        orders[index] = order
        execution[index] = block
    frame = pd.DataFrame(rows)
    frame.to_csv(O / "strategies" / f"Q4-2-{strategy}.daily.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    np.savez_compressed(O / "strategies" / f"Q4-2-{strategy}.npz", days=np.arange(START, 365),
                        order=orders, execution=execution)
    result = summarize(frame, "Q4-2", strategy, metrics(prices, forecast, "Q4-2"), executable)
    print(json.dumps({"event": "strategy_complete", "branch": "Q4-2", "strategy": strategy,
                      "cost": result["total_cost"], "lp_calls": budget.lp_calls}, ensure_ascii=False), flush=True)
    budget.save()
    return result


def run_q43(strategy, forecast, prices, base, source, executable=True):
    planner = q4.Q43Planner(terminal_value=0.9 * base[0])
    state = COMMON
    qzero = np.empty((334, 144))
    versions = np.empty((334, 4, 144))
    execution = np.empty((334, 144, len(q4.EXEC_COLUMNS)))
    rows = []
    for index, day in enumerate(range(START, q4.N_DAYS)):
        initial = state
        order = np.zeros(144)
        for ri, release in enumerate(RELEASES):
            batch = day * 4 + ri
            n = 288 - release
            planned = planner.solve(source["q3_load"][day, release:release+n], source["q3_pv"][batch, :n], state,
                                    source["q3_margin"][batch, :n], release,
                                    None if release == 0 else qzero[index, release:], forecast[batch, :n],
                                    {"branch": "Q4-3", "strategy": strategy, "day": day, "release_slot": release})
            order[release:] = planned[:144-release]
            if release == 0:
                qzero[index] = order.copy()
            versions[index, ri] = order
            truth = source["q3_actual"][day*144+release:day*144+release+36]
            block, state = q4.execute_block(truth[:, 0], truth[:, 1], order[release:release+36], state)
            execution[index, release:release+36] = block
        delta = order - qzero[index]
        energy = float(prices[day] @ order)
        adjustment = float(0.5 * prices[day] @ np.abs(delta))
        emergency = float(5 * prices[day] @ execution[index, :, 8])
        rows.append({"branch": "Q4-3", "strategy": strategy, "day": day, "date": q4.daystr(day),
                     "initial": initial, "final": state, "ordinary_cost": energy,
                     "adjustment_cost": adjustment, "ordinary_settlement_cost": energy + adjustment,
                     "emergency_cost": emergency, "total_cost": energy + adjustment + emergency,
                     "order_kwh": float(order.sum()), "emergency_kwh": float(execution[index, :, 8].sum()),
                     "unused_order_kwh": float(execution[index, :, 9].sum()),
                     "unused_pv_kwh": float(execution[index, :, 10].sum()),
                     "reduced_kwh": float(np.maximum(-delta, 0).sum()),
                     "increased_kwh": float(np.maximum(delta, 0).sum())})
    frame = pd.DataFrame(rows)
    frame.to_csv(O / "strategies" / f"Q4-3-{strategy}.daily.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    np.savez_compressed(O / "strategies" / f"Q4-3-{strategy}.npz", days=np.arange(START, 365),
                        q0=qzero, versions=versions, execution=execution)
    result = summarize(frame, "Q4-3", strategy, metrics(prices, forecast, "Q4-3"), executable)
    print(json.dumps({"event": "strategy_complete", "branch": "Q4-3", "strategy": strategy,
                      "cost": result["total_cost"], "lp_calls": budget.lp_calls}, ensure_ascii=False), flush=True)
    budget.save()
    return result


def copy_baseline(branch, old_name, new_name, price_metrics):
    old_root = OLD / "outputs/common_start"
    daily = pd.read_csv(old_root / f"{branch}-{old_name}.daily.csv", float_precision="round_trip")
    daily["strategy"] = new_name
    if "candidate" in daily:
        daily = daily.drop(columns="candidate")
    daily.to_csv(O / "strategies" / f"{branch}-{new_name}.daily.csv", index=False,
                 encoding="utf-8-sig", float_format="%.17g")
    shutil.copy2(old_root / f"{branch}-{old_name}.npz", O / "strategies" / f"{branch}-{new_name}.npz")
    return summarize(daily, branch, new_name, price_metrics, True)


def make_information_forecasts(base_forecast):
    variants = {}
    freeze = np.full_like(base_forecast, np.nan)
    for day in range(START, q4.N_DAYS):
        q0 = base_forecast[day * 4]
        for ri, release in enumerate(RELEASES):
            n = 288 - release
            freeze[day * 4 + ri, :n] = q0[release:release+n]
    variants["P2-freeze-midnight-price"] = freeze
    for omit_index, omit_hour in ((1, 6), (2, 12), (3, 18)):
        arr = base_forecast.copy()
        for day in range(START, q4.N_DAYS):
            n = 288 - RELEASES[omit_index]
            previous = base_forecast[day * 4 + omit_index - 1]
            arr[day * 4 + omit_index, :n] = previous[36:36+n]
        variants[f"P2-omit-{omit_hour:02d}-price-update"] = arr
    return variants


def perfect_q42(selected, prices):
    out = selected.copy()
    flat = prices.reshape(-1)
    for day in range(START, q4.N_DAYS):
        targets = day * 144 + np.arange(288)
        valid = targets < len(flat)
        out[day, valid] = flat[targets[valid]]
    return out


def perfect_q43(selected, prices):
    out = selected.copy()
    flat = prices.reshape(-1)
    for day in range(START, q4.N_DAYS):
        for ri, release in enumerate(RELEASES):
            n = 288 - release
            targets = day * 144 + release + np.arange(n)
            valid = targets < len(flat)
            out[day * 4 + ri, :n][valid] = flat[targets[valid]]
    return out


def main():
    if O.exists():
        raise FileExistsError(f"Refusing overwrite: {O}")
    O.mkdir()
    (O / "strategies").mkdir()
    (O / "price_forecasts").mkdir()
    verify_sources()
    prices, base, _ = q4.load_prices_and_base()
    source = dict(np.load(OLD / "outputs/supply_inputs.npz"))
    old_forecasts = dict(np.load(OLD / "outputs/price_forecasts.npz"))
    old_candidates = [str(x) for x in old_forecasts["candidates"]]
    p2i, p3i = old_candidates.index("P2"), old_candidates.index("P3")
    q42_selected = old_forecasts["q42"][p3i]
    q43_selected = old_forecasts["q43"][p2i]
    old_results = pd.DataFrame(json.loads((OLD / "outputs/summary.json").read_text(encoding="utf-8"))["candidates"])
    p3_metrics = old_results[(old_results.branch == "Q4-2") & (old_results.candidate == "P3")].iloc[0]
    p2_metrics = old_results[(old_results.branch == "Q4-3") & (old_results.candidate == "P2")].iloc[0]
    metric_names = ["price_mae", "price_rmse", "top5_price_mae", "evening_price_mae", "price_bias", "top5_threshold"]

    results = [
        copy_baseline("Q4-2", "P3", "P3-full", {x: float(p3_metrics[x]) for x in metric_names}),
        copy_baseline("Q4-3", "P2", "P2-full", {x: float(p2_metrics[x]) for x in metric_names}),
    ]

    q42_supply = {"load": source["q2_load"], "pv": source["q2_pv"]}
    q43_supply = {"load": source["q3_load"], "pv": source["q3_pv"]}
    f42 = q4.PriceFeatures(prices, base, q42_supply, "Q4-2")
    f43 = q4.PriceFeatures(prices, base, q43_supply, "Q4-3")
    q42_engines = [
        ForecastEngine("P3-no-net", f42, "p3", feature_mode="no_net"),
        ForecastEngine("P3-history-only", f42, "p3", feature_mode="history_only"),
        ForecastEngine("P3-window28", f42, "p3", window=28),
        ForecastEngine("P3-window84", f42, "p3", window=84),
        ForecastEngine("P3-leaves7", f42, "p3", max_leaf_nodes=7),
        ForecastEngine("P3-leaves31", f42, "p3", max_leaf_nodes=31),
    ]
    for engine in q42_engines:
        forecast = build_forecast(engine)
        results.append(run_q42(engine.name, forecast, prices, base, source))

    q43_engines = [
        ForecastEngine("P2-residual-a10", f43, "p2_residual", alpha=10),
        ForecastEngine("P2-residual-no-net", f43, "p2_residual", alpha=10, feature_mode="residual_no_net"),
        ForecastEngine("P2-residual-a1", f43, "p2_residual", alpha=1),
        ForecastEngine("P2-residual-a100", f43, "p2_residual", alpha=100),
    ]
    for engine in q43_engines:
        forecast = build_forecast(engine)
        results.append(run_q43(engine.name, forecast, prices, base, source))

    for name, forecast in make_information_forecasts(q43_selected).items():
        np.savez_compressed(O / "price_forecasts" / f"{name}.npz", values=forecast)
        results.append(run_q43(name, forecast, prices, base, source))

    ideal42 = perfect_q42(q42_selected, prices)
    ideal43 = perfect_q43(q43_selected, prices)
    np.savez_compressed(O / "price_forecasts/Q4-2-perfect-price-info.npz", values=ideal42)
    np.savez_compressed(O / "price_forecasts/Q4-3-perfect-price-info.npz", values=ideal43)
    results.append(run_q42("perfect-price-info", ideal42, prices, base, source, executable=False))
    results.append(run_q43("perfect-price-info", ideal43, prices, base, source, executable=False))

    frame = pd.DataFrame(results)
    frame.to_csv(O / "comparison.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    result = {
        "status": "completed_pending_independent_verification_and_interpretation",
        "official_period": ["2025-02-01", "2025-12-31"],
        "common_initial_kwh": COMMON,
        "results": results,
        "budget": {"lp_calls": budget.lp_calls, "price_model_fits": budget.price_fits,
                   "elapsed_seconds": time.perf_counter() - budget.start},
        "protocol_sha256": sha(R / "protocol.json"), "code_sha256": sha(__file__),
    }
    dump(O / "summary.json", result)
    budget.save()
    dump(O / "environment.json", {
        "python": __import__("platform").python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "sklearn": __import__("sklearn").__version__, "threads": 1,
    })
    print(json.dumps({"event": "complete", "strategies": len(results),
                      "lp_calls": budget.lp_calls, "price_fits": budget.price_fits}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        logs.close()
