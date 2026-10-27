"""Independent read-back verification for the approved Q4 deepening run."""
from decimal import Decimal, getcontext
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

getcontext().prec = 50
R = Path(__file__).resolve().parent
P = R.parents[3]
OLD = R.parent / "20260912-three-candidates-v1"
O = R / "outputs"
START = 31
COMMON = 8592.693560925925
CAP = 5000 / 6


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


protocol = json.loads((R / "protocol.json").read_text(encoding="utf-8"))
for rel, expected in protocol["source_sha256"].items():
    assert sha(P / rel) == expected

price_frame = pd.read_csv(P / "data/prepared-v1/actual_price.csv", float_precision="round_trip")
price_frame["day"] = (pd.to_datetime(price_frame.source_date) - pd.Timestamp("2025-01-01")).dt.days
price_frame["slot"] = (price_frame.source_minute.astype(int) % 1440) // 10
price = price_frame.pivot(index="day", columns="slot", values="price_yuan_per_kwh").reindex(
    index=range(365), columns=range(144)
).to_numpy()
assert np.isfinite(price).all()

source = dict(np.load(OLD / "outputs/supply_inputs.npz"))
actual42 = source["q2_actual"]
actual43 = source["q3_actual"][:365 * 144].reshape(365, 144, 2)
old_forecast = dict(np.load(OLD / "outputs/price_forecasts.npz"))
old_names = [str(x) for x in old_forecast["candidates"]]

summary = json.loads((O / "summary.json").read_text(encoding="utf-8"))
summary_map = {(x["branch"], x["strategy"]): x for x in summary["results"]}
files = sorted((O / "strategies").glob("*.daily.csv"))
assert len(files) == 18
assert not any("P4" in x.name or "scenario" in x.name.lower() for x in files)

maxima = {"storage": 0.0, "balance": 0.0, "unused_order": 0.0,
          "unused_pv": 0.0, "prefix": 0.0, "daily_cost": 0.0, "aggregate_cost": 0.0}
checked_intervals = checked_days = 0


def forecast_for(branch, strategy):
    if branch == "Q4-2" and strategy == "P3-full":
        return old_forecast["q42"][old_names.index("P3")]
    if branch == "Q4-3" and strategy == "P2-full":
        return old_forecast["q43"][old_names.index("P2")]
    if strategy == "perfect-price-info":
        path = O / "price_forecasts" / f"{branch}-perfect-price-info.npz"
    else:
        path = O / "price_forecasts" / f"{strategy}.npz"
    return np.load(path)["values"]


def price_metrics(branch, forecast):
    actuals, preds = [], []
    if branch == "Q4-2":
        for day in range(START, 365):
            actuals.append(price[day])
            preds.append(forecast[day, :144])
    else:
        for day in range(START, 365):
            for ri in range(4):
                actuals.append(price[day, ri*36:(ri+1)*36])
                preds.append(forecast[day*4+ri, :36])
    actual = np.concatenate(actuals)
    pred = np.concatenate(preds)
    err = abs(actual - pred)
    high = actual >= np.quantile(price[START:], .95)
    evening_slots = np.tile(np.arange(144), 365 - START)
    evening = (evening_slots >= 19*6) & (evening_slots < 22*6)
    return {
        "price_mae": float(err.mean()),
        "price_rmse": float(np.sqrt(np.mean((actual - pred)**2))),
        "top5_price_mae": float(err[high].mean()),
        "evening_price_mae": float(err[evening].mean()),
        "price_bias": float(np.mean(pred - actual)),
    }


for daily_path in files:
    daily = pd.read_csv(daily_path, float_precision="round_trip")
    branch = str(daily.branch.iloc[0])
    strategy = str(daily.strategy.iloc[0])
    row = summary_map[(branch, strategy)]
    assert len(daily) == 334 and list(daily.day) == list(range(START, 365))
    trace = dict(np.load(O / "strategies" / daily_path.name.replace(".daily.csv", ".npz")))
    execution = trace["execution"]
    order = trace["order"] if branch == "Q4-2" else trace["versions"][:, -1]
    assert execution.shape == (334, 144, 12) and order.shape == (334, 144)
    assert np.isfinite(execution).all() and np.isfinite(order).all() and np.min(order) >= -1e-8

    if branch == "Q4-3":
        q0, versions = trace["q0"], trace["versions"]
        assert np.max(abs(q0 - versions[:, 0])) < 1e-10
        for release in range(1, 4):
            slot = release * 36
            maxima["prefix"] = max(maxima["prefix"], float(np.max(abs(
                versions[:, release, :slot] - versions[:, release-1, :slot]
            ))))

    starts, ends = execution[:, :, 0], execution[:, :, 1]
    assert abs(starts[0, 0] - COMMON) < 1e-9
    maxima["storage"] = max(maxima["storage"],
        float(np.max(abs(ends[:, :-1] - starts[:, 1:]))),
        float(np.max(abs(ends[:-1, -1] - starts[1:, 0]))))
    change = .9 * (execution[:, :, 5] + execution[:, :, 6]) - execution[:, :, 7] / .9
    maxima["storage"] = max(maxima["storage"], float(np.max(abs(ends - starts - change))))
    assert np.min(starts) >= 1200 - 1e-6 and np.max(ends) <= 10800 + 1e-6
    assert np.max(execution[:, :, 5] + execution[:, :, 6]) <= CAP + 1e-6
    assert np.max(execution[:, :, 7]) <= CAP + 1e-6
    assert not np.any(((execution[:, :, 5] + execution[:, :, 6]) > 1e-7) & (execution[:, :, 7] > 1e-7))
    balance = execution[:, :, 2] - execution[:, :, 5] + execution[:, :, 4] + execution[:, :, 7] + execution[:, :, 8] - execution[:, :, 11]
    maxima["balance"] = max(maxima["balance"], float(np.max(abs(balance))))
    maxima["unused_order"] = max(maxima["unused_order"], float(np.max(abs(
        execution[:, :, 9] - np.maximum(order - execution[:, :, 2], 0)
    ))))
    actual = actual42[START:] if branch == "Q4-2" else actual43[START:]
    pv_energy = actual[:, :, 1] / 6
    maxima["unused_pv"] = max(maxima["unused_pv"], float(np.max(abs(
        execution[:, :, 10] - np.maximum(pv_energy - execution[:, :, 4] - execution[:, :, 6], 0)
    ))))
    assert max(maxima["storage"], maxima["balance"], maxima["unused_order"], maxima["unused_pv"], maxima["prefix"]) < 1e-6

    actual_price = price[START:]
    energy = np.sum(actual_price * order, axis=1)
    adjustment = np.zeros(334) if branch == "Q4-2" else .5 * np.sum(actual_price * abs(order - trace["q0"]), axis=1)
    emergency = 5 * np.sum(actual_price * execution[:, :, 8], axis=1)
    total = energy + adjustment + emergency
    maxima["daily_cost"] = max(maxima["daily_cost"], float(np.max(abs(daily.total_cost.to_numpy() - total))))
    assert np.max(abs(daily.ordinary_cost.to_numpy() - energy)) < 1e-6
    assert np.max(abs(daily.adjustment_cost.to_numpy() - adjustment)) < 1e-6
    assert np.max(abs(daily.emergency_cost.to_numpy() - emergency)) < 1e-6

    dec_energy = Decimal(0)
    dec_adjust = Decimal(0)
    dec_emergency = Decimal(0)
    for di in range(334):
        for slot in range(144):
            p = Decimal(str(actual_price[di, slot]))
            dec_energy += p * Decimal(str(order[di, slot]))
            if branch == "Q4-3":
                dec_adjust += Decimal("0.5") * p * Decimal(str(abs(order[di, slot] - trace["q0"][di, slot])))
            dec_emergency += Decimal(5) * p * Decimal(str(execution[di, slot, 8]))
    maxima["aggregate_cost"] = max(maxima["aggregate_cost"], abs(float(dec_energy + dec_adjust + dec_emergency) - row["total_cost"]))
    assert abs(float(dec_energy) - row["ordinary_cost"]) < 1e-6
    assert abs(float(dec_adjust) - row["adjustment_cost"]) < 1e-6
    assert abs(float(dec_emergency) - row["emergency_cost"]) < 1e-6
    assert abs(float(dec_energy + dec_adjust + dec_emergency) - row["total_cost"]) < 1e-6
    assert abs(float(ends[-1, -1]) - row["final_kwh"]) < 1e-8

    recalculated = price_metrics(branch, forecast_for(branch, strategy))
    for key, value in recalculated.items():
        assert abs(value - row[key]) < 1e-10, (branch, strategy, key, value, row[key])
    checked_intervals += 334 * 144
    checked_days += 334

fit_rows = [json.loads(x) for x in (O / "price_fit_log.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(fit_rows) == 490
for row in fit_rows:
    assert row["cutoff_datetime"] == row["latest_target_end"]
    assert row["training_rows"] >= 500
    path = R / row["model_path"]
    assert sha(path) == row["model_sha256"]

forecast_rows = [json.loads(x) for x in (O / "price_forecast_log.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(forecast_rows) == 7348
assert all(row["fit_cutoff_day"] <= row["decision_day"] for row in forecast_rows)

solver_rows = [json.loads(x) for x in (O / "solver_checks.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(solver_rows) == 14362
assert all(x["status"] == 0 and x["simultaneous"] == 0 for x in solver_rows)
assert max(x["residual"] for x in solver_rows) < 1e-6
assert max(x["dual_gap"] for x in solver_rows) < 1e-4

budget = json.loads((O / "budget.json").read_text(encoding="utf-8"))
assert budget["lp_calls"] == len(solver_rows) <= protocol["hard_budget"]["new_lp_calls"]
assert budget["price_model_fits"] == len(fit_rows) <= protocol["hard_budget"]["new_price_model_fits"]

verification = {
    "status": "verified_by_independent_readback_not_human_review",
    "research_recomputed": {"price_fits": 0, "lp_calls": 0},
    "checked": {"strategies": len(files), "days": checked_days, "intervals": checked_intervals,
                "saved_solver_records": len(solver_rows), "saved_price_models": len(fit_rows),
                "saved_forecast_calls": len(forecast_rows)},
    "max_residuals": maxima,
    "source_sha256": protocol["source_sha256"],
    "protocol_sha256": sha(R / "protocol.json"),
    "run_code_sha256": sha(R / "run_deepening.py"),
    "verification_code_sha256": sha(__file__),
    "boundary": "Checks saved arithmetic, physical feasibility, billing, order locking, causal training cutoffs, source hashes and budgets. Perfect-price strategies are explicitly non-executable references. No cross-year or human validation is claimed."
}
dump(O / "verification.json", verification)
print(json.dumps({"status": verification["status"], "strategies": len(files),
                  "max_cost_difference": maxima["aggregate_cost"]}, ensure_ascii=False))
