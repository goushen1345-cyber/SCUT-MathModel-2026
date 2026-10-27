"""Independent read-back checks for the Q4 same-start P1--P3 comparison; no fitting or LP."""
from decimal import Decimal, getcontext
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

getcontext().prec = 50
R = Path(__file__).resolve().parent
P = R.parents[3]
O = R / "outputs"
C = O / "common_start"
START = 31
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

power = pd.read_csv(P / "data/prepared-v1/actual_power.csv", float_precision="round_trip")
start = pd.to_datetime(power.source_date) + pd.to_timedelta(power.source_minute, unit="m")
power["day"] = (start.dt.normalize() - pd.Timestamp("2025-01-01")).dt.days
power["slot"] = start.dt.hour * 6 + start.dt.minute // 10
ref = pd.read_csv(P / "data/prepared-v1/day_reference.csv", float_precision="round_trip")
ref["slot"] = (ref.source_minute.astype(int) % 1440) // 10
ref = ref.sort_values("slot")
actual = np.full((365, 144, 2), np.nan)
for vi, col in enumerate(("load_kw", "pv_actual_kw")):
    actual[:, :, vi] = power.pivot(index="day", columns="slot", values=col).reindex(
        index=range(365), columns=range(144)
    ).to_numpy()
actual[0, 0] = ref.loc[ref.slot == 0, ["load_kw", "pv_forecast_kw"]].to_numpy()[0]
assert np.isfinite(actual).all()

summary = json.loads((C / "summary.json").read_text(encoding="utf-8"))
summary_map = {(row["branch"], row["candidate"]): row for row in summary["results"]}
maxima = {"balance": 0.0, "storage": 0.0, "cost": 0.0, "daily": 0.0,
          "unused_order": 0.0, "unused_pv": 0.0, "prefix": 0.0}
checked_slots = checked_days = 0

for branch in ("Q4-2", "Q4-3"):
    for candidate in ("P1", "P2", "P3"):
        trace = dict(np.load(C / f"{branch}-{candidate}.npz"))
        daily = pd.read_csv(C / f"{branch}-{candidate}.daily.csv", float_precision="round_trip")
        assert len(daily) == 334 and list(daily.day) == list(range(31, 365))
        execution = trace["execution"]
        order = trace["order"] if branch == "Q4-2" else trace["versions"][:, -1]
        assert execution.shape == (334, 144, 12) and order.shape == (334, 144)
        assert np.isfinite(execution).all() and np.isfinite(order).all() and np.min(order) >= -1e-8

        if branch == "Q4-3":
            q0, versions = trace["q0"], trace["versions"]
            assert np.max(abs(q0 - versions[:, 0])) < 1e-10
            for release in range(1, 4):
                slot = release * 36
                maxima["prefix"] = max(maxima["prefix"], float(np.max(abs(versions[:, release, :slot] - versions[:, release-1, :slot]))))
            assert maxima["prefix"] < 1e-10

        starts, ends = execution[:, :, 0], execution[:, :, 1]
        maxima["storage"] = max(maxima["storage"], float(np.max(abs(ends[:, :-1] - starts[:, 1:]))),
                                float(np.max(abs(ends[:-1, -1] - starts[1:, 0]))))
        assert abs(starts[0, 0] - 8592.693560925925) < 1e-9
        assert np.min(starts) >= 1200 - 1e-6 and np.max(ends) <= 10800 + 1e-6
        storage_change = 0.9 * (execution[:, :, 5] + execution[:, :, 6]) - execution[:, :, 7] / 0.9
        maxima["storage"] = max(maxima["storage"], float(np.max(abs(ends - starts - storage_change))))
        balance = execution[:, :, 2] - execution[:, :, 5] + execution[:, :, 4] + execution[:, :, 7] + execution[:, :, 8] - execution[:, :, 11]
        maxima["balance"] = max(maxima["balance"], float(np.max(abs(balance))))
        assert np.max(execution[:, :, 5] + execution[:, :, 6]) <= CAP + 1e-6
        assert np.max(execution[:, :, 7]) <= CAP + 1e-6
        assert not np.any(((execution[:, :, 5] + execution[:, :, 6]) > 1e-7) & (execution[:, :, 7] > 1e-7))
        maxima["unused_order"] = max(maxima["unused_order"], float(np.max(abs(execution[:, :, 9] - np.maximum(order - execution[:, :, 2], 0)))))
        actual_slice = actual[START:]
        pv_energy = actual_slice[:, :, 1] / 6
        maxima["unused_pv"] = max(maxima["unused_pv"], float(np.max(abs(execution[:, :, 10] - np.maximum(pv_energy - execution[:, :, 4] - execution[:, :, 6], 0)))))
        assert max(maxima["balance"], maxima["storage"], maxima["unused_order"], maxima["unused_pv"]) < 1e-6

        actual_price = price[START:]
        if branch == "Q4-2":
            energy = np.sum(actual_price * order, axis=1)
            adjustment = np.zeros(334)
        else:
            energy = np.sum(actual_price * order, axis=1)
            adjustment = 0.5 * np.sum(actual_price * abs(order - trace["q0"]), axis=1)
        emergency = 5 * np.sum(actual_price * execution[:, :, 8], axis=1)
        total = energy + adjustment + emergency
        maxima["daily"] = max(maxima["daily"], float(np.max(abs(daily.total_cost.to_numpy() - total))))
        assert np.max(abs(daily.ordinary_cost.to_numpy() - energy)) < 1e-6
        assert np.max(abs(daily.adjustment_cost.to_numpy() - adjustment)) < 1e-6
        assert np.max(abs(daily.emergency_cost.to_numpy() - emergency)) < 1e-6

        # Decimal recomputation of the aggregate bill from saved arrays and original prices.
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
        row = summary_map[(branch, candidate)]
        dec_total = dec_energy + dec_adjust + dec_emergency
        maxima["cost"] = max(maxima["cost"], abs(float(dec_total) - row["total_cost"]))
        assert abs(float(dec_energy) - row["ordinary_cost"]) < 1e-6
        assert abs(float(dec_adjust) - row["adjustment_cost"]) < 1e-6
        assert abs(float(dec_emergency) - row["emergency_cost"]) < 1e-6
        assert abs(float(dec_total) - row["total_cost"]) < 1e-6
        assert abs(float(ends[-1, -1]) - row["final_kwh"]) < 1e-8
        checked_slots += 334 * 144
        checked_days += 334

# Forecast and causality metadata checks.
forecast = dict(np.load(O / "price_forecasts.npz"))
assert forecast["q42"].shape == (3, 365, 288) and forecast["q43"].shape == (3, 1460, 288)
assert np.isfinite(forecast["q42"]).all()
for batch in range(1460):
    n = 288 - (batch % 4) * 36
    assert np.isfinite(forecast["q43"][:, batch, :n]).all()
    assert np.isnan(forecast["q43"][:, batch, n:]).all()
assert np.min(forecast["q42"]) > 0 and np.nanmin(forecast["q43"]) > 0

fit_rows = [json.loads(line) for line in (O / "price_fit_log.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(fit_rows) == 208
for row in fit_rows:
    assert row["candidate"] in {"P2", "P3"}
    assert row["training_rows"] >= 500
    assert row["latest_target_end"] == row["cutoff_datetime"]
    model_path = R / row["model_path"]
    assert sha(model_path) == row["model_sha256"]

solver_rows = [json.loads(line) for line in (C / "solver_checks.jsonl").read_text(encoding="utf-8").splitlines()]
assert len(solver_rows) == 5010
assert all(row["status"] == 0 and row["simultaneous"] == 0 for row in solver_rows)
assert max(row["residual"] for row in solver_rows) < 1e-6
assert max(row["dual_gap"] for row in solver_rows) < 1e-4

comparison = pd.read_csv(C / "comparison.csv", float_precision="round_trip")
assert comparison.groupby("branch").first().candidate.to_dict() == {"Q4-2": "P3", "Q4-3": "P3"}

verification = {
    "status": "verified_by_independent_readback_not_human_review",
    "research_recomputed": {"price_fits": 0, "lp_calls": 0},
    "checked": {"strategies": 6, "days": checked_days, "intervals": checked_slots,
                "saved_solver_records": len(solver_rows), "saved_price_models": len(fit_rows)},
    "max_residuals": maxima,
    "source_sha256": protocol["source_sha256"],
    "main_protocol_sha256": sha(R / "protocol.json"),
    "control_protocol_sha256": sha(R / "common_start_protocol.json"),
    "run_code_sha256": sha(R / "run_compare.py"),
    "control_code_sha256": sha(R / "common_start.py"),
    "verification_code_sha256": sha(__file__),
    "selection": {"Q4-2": "P3", "Q4-3": "P3"},
    "boundary": "Checks saved arithmetic, physical feasibility, billing, order-prefix locking, source hashes and causal cutoffs; does not create an external-year generalization test or human approval."
}
dump(O / "verification.json", verification)
print(json.dumps({"status": verification["status"], "selection": verification["selection"],
                  "max_cost_difference": maxima["cost"]}, ensure_ascii=False))
