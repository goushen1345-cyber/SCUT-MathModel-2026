"""Same-Feb-1-storage control for the completed Q4 P1--P3 comparison."""
from pathlib import Path
import csv
import importlib.util
import json
import time

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q4run", R / "run_compare.py")
q4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q4)

C = R / "outputs" / "common_start"
assert not C.exists(), C
C.mkdir()
COMMON = 8592.693560925925
START = 31
start_time = time.perf_counter()


class ControlBudget:
    def __init__(self):
        self.lp_calls = 0
        self.price_fits = 0

    def check(self):
        assert self.lp_calls <= 5200
        assert time.perf_counter() - start_time <= 900


class ControlLogs:
    def __init__(self):
        self.handle = (C / "solver_checks.jsonl").open("w", encoding="utf-8")

    def event(self, name, row):
        if name == "solver_checks":
            self.handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def close(self):
        self.handle.close()


q4.budget = ControlBudget()
q4.logs = ControlLogs()


def summary(frame, branch, candidate):
    return {
        "branch": branch, "candidate": candidate, "days": len(frame),
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
    }


def q42_run(candidate, ci, forecasts, prices, base, source):
    planner = q4.Q42Planner(terminal_value=.9 * base[0])
    state = COMMON
    orders = np.empty((334, 144))
    execution = np.empty((334, 144, len(q4.EXEC_COLUMNS)))
    rows = []
    for index, day in enumerate(range(START, 365)):
        initial = state
        order = planner.solve(source["q2_load"][day], source["q2_pv"][day], state,
                              source["q2_margin"][day], forecasts[ci, day],
                              {"control": "common_start", "branch": "Q4-2", "candidate": candidate,
                               "day": day, "release_slot": 0})[:144]
        block, state = q4.execute_block(source["q2_actual"][day, :, 0], source["q2_actual"][day, :, 1], order, state)
        ordinary = float(prices[day] @ order)
        emergency = float(5 * prices[day] @ block[:, 8])
        rows.append({"branch": "Q4-2", "candidate": candidate, "day": day, "date": q4.daystr(day),
                     "initial": initial, "final": state, "ordinary_cost": ordinary, "adjustment_cost": 0.,
                     "ordinary_settlement_cost": ordinary, "emergency_cost": emergency,
                     "total_cost": ordinary + emergency, "order_kwh": float(order.sum()),
                     "emergency_kwh": float(block[:, 8].sum()), "unused_order_kwh": float(block[:, 9].sum()),
                     "unused_pv_kwh": float(block[:, 10].sum())})
        orders[index] = order
        execution[index] = block
    frame = pd.DataFrame(rows)
    frame.to_csv(C / f"Q4-2-{candidate}.daily.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    np.savez_compressed(C / f"Q4-2-{candidate}.npz", days=np.arange(START, 365), order=orders, execution=execution)
    return summary(frame, "Q4-2", candidate)


def q43_run(candidate, ci, forecasts, prices, base, source):
    planner = q4.Q43Planner(terminal_value=.9 * base[0])
    state = COMMON
    qzero = np.empty((334, 144))
    versions = np.empty((334, 4, 144))
    execution = np.empty((334, 144, len(q4.EXEC_COLUMNS)))
    rows = []
    for index, day in enumerate(range(START, 365)):
        initial = state
        order = np.zeros(144)
        for release_index, slot in enumerate((0, 36, 72, 108)):
            batch = day * 4 + release_index
            n = 288 - slot
            planned = planner.solve(source["q3_load"][day, slot:slot+n], source["q3_pv"][batch, :n], state,
                                    source["q3_margin"][batch, :n], slot,
                                    None if slot == 0 else qzero[index, slot:], forecasts[ci, batch, :n],
                                    {"control": "common_start", "branch": "Q4-3", "candidate": candidate,
                                     "day": day, "release_slot": slot})
            order[slot:] = planned[:144-slot]
            if slot == 0:
                qzero[index] = order.copy()
            versions[index, release_index] = order
            truth = source["q3_actual"][day*144+slot:day*144+slot+36]
            block, state = q4.execute_block(truth[:, 0], truth[:, 1], order[slot:slot+36], state)
            execution[index, slot:slot+36] = block
        delta = order - qzero[index]
        energy_cost = float(prices[day] @ order)
        adjustment = float(.5 * prices[day] @ abs(delta))
        emergency = float(5 * prices[day] @ execution[index, :, 8])
        rows.append({"branch": "Q4-3", "candidate": candidate, "day": day, "date": q4.daystr(day),
                     "initial": initial, "final": state, "ordinary_cost": energy_cost,
                     "adjustment_cost": adjustment, "ordinary_settlement_cost": energy_cost + adjustment,
                     "emergency_cost": emergency, "total_cost": energy_cost + adjustment + emergency,
                     "order_kwh": float(order.sum()), "emergency_kwh": float(execution[index, :, 8].sum()),
                     "unused_order_kwh": float(execution[index, :, 9].sum()),
                     "unused_pv_kwh": float(execution[index, :, 10].sum()),
                     "reduced_kwh": float(np.maximum(-delta, 0).sum()),
                     "increased_kwh": float(np.maximum(delta, 0).sum())})
    frame = pd.DataFrame(rows)
    frame.to_csv(C / f"Q4-3-{candidate}.daily.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    np.savez_compressed(C / f"Q4-3-{candidate}.npz", days=np.arange(START, 365), q0=qzero,
                        versions=versions, execution=execution)
    return summary(frame, "Q4-3", candidate)


def main():
    prices, base, _ = q4.load_prices_and_base()
    source = dict(np.load(R / "outputs" / "supply_inputs.npz"))
    forecast = dict(np.load(R / "outputs" / "price_forecasts.npz"))
    candidates = [str(x) for x in forecast["candidates"]]
    rows = []
    for ci, candidate in enumerate(candidates):
        rows.append(q42_run(candidate, ci, forecast["q42"], prices, base, source))
    for ci, candidate in enumerate(candidates):
        rows.append(q43_run(candidate, ci, forecast["q43"], prices, base, source))
    frame = pd.DataFrame(rows).sort_values(["branch", "total_cost"])
    frame.to_csv(C / "comparison.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    result = {"status": "completed_pending_independent_verification", "common_initial_kwh": COMMON,
              "official_period": ["2025-02-01", "2025-12-31"], "results": rows,
              "winners": {branch: frame[frame.branch == branch].iloc[0].candidate for branch in ("Q4-2", "Q4-3")},
              "lp_calls": q4.budget.lp_calls, "price_fits": 0,
              "elapsed_seconds": time.perf_counter() - start_time,
              "protocol_sha256": q4.sha(R / "common_start_protocol.json"),
              "code_sha256": q4.sha(__file__)}
    q4.dump(C / "summary.json", result)
    print(json.dumps({"event": "common_start_complete", "winners": result["winners"],
                      "lp_calls": q4.budget.lp_calls}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    finally:
        q4.logs.close()
