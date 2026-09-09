"""Execute the U015-approved Q2-DEEPEN-v1 W1 solve and scenario generation."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import math
import random
import shutil
import time
import types

import highspy
import numpy as np


_trial_path = Path(__file__).with_name("run_trials.py")
_trial_source = _trial_path.read_text(encoding="utf-8")
_trial_source = _trial_source.replace(
    "assert state['stage']=='TRIAL' and state['active_question']=='Q2'",
    "assert state['stage'] in ('TRIAL','DEEPEN') and state['active_question']=='Q2'",
)
r = types.ModuleType("q2_trial_readonly_reuse")
r.__file__ = str(_trial_path)
exec(compile(_trial_source, str(_trial_path), "exec"), r.__dict__)


ROOT = r.ROOT
Q = r.Q
OUT = Q / "deep_runs"
SCEN = OUT / "scenarios"
DATA = r.DATA
YEARS = r.YEARS
INF = highspy.kHighsInf


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def writecsv(path, rows):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rows_from_vals(md, vals, label):
    rows = []
    for (lid, year, season, crop), j in md.x.items():
        if vals[j] > 1e-7:
            rows.append(
                {
                    "candidate": label,
                    "year": year,
                    "season": season,
                    "land_id": lid,
                    "land_type": r.lands[lid]["land_type"],
                    "crop_id": crop,
                    "crop_name": r.crops[crop]["crop_name"],
                    "area_mu": f"{vals[j]:.10g}",
                }
            )
    return rows


def solve_custom(md, seconds, start, costs=None, extra_rows=(), gap=0.001):
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("time_limit", float(seconds))
    h.setOptionValue("random_seed", r.SEED)
    h.setOptionValue("mip_rel_gap", float(gap))
    assert h.passModel(md.lp) == highspy.HighsStatus.kOk
    if costs is not None:
        idx = np.arange(len(costs), dtype=np.int32)
        assert h.changeColsCost(len(costs), idx, np.asarray(costs, dtype=float)) == highspy.HighsStatus.kOk
    for co, lo, hi in extra_rows:
        idx = np.asarray(sorted(co), dtype=np.int32)
        val = np.asarray([co[j] for j in idx], dtype=float)
        assert h.addRow(float(lo), float(hi), len(idx), idx, val) == highspy.HighsStatus.kOk
    warm = highspy.HighsSolution()
    warm.col_value = list(map(float, start))
    warm.value_valid = True
    assert h.setSolution(warm) == highspy.HighsStatus.kOk
    began = time.perf_counter()
    h.run()
    elapsed = time.perf_counter() - began
    solution = h.getSolution()
    info = h.getInfo()
    vals = np.asarray(solution.col_value) if solution.value_valid else np.zeros(len(md.meta))
    return vals, {
        "status": h.modelStatusToString(h.getModelStatus()),
        "solution_valid": bool(solution.value_valid),
        "runtime_seconds": elapsed,
        "objective_value": float(h.getObjectiveValue()) if solution.value_valid else None,
        "mip_gap": float(getattr(info, "mip_gap", math.nan)),
        "mip_dual_bound": float(getattr(info, "mip_dual_bound", math.nan)),
        "mip_node_count": int(getattr(info, "mip_node_count", -1)),
        "simplex_iterations": int(getattr(info, "simplex_iteration_count", -1)),
    }


def profit(md, vals):
    return float(sum(vals[j] * v for j, v in md.profit_coefs[0].items()))


def activations(md, vals):
    return int(sum(vals[j] > 0.5 for j in md.z.values()))


def run_w1():
    out = OUT / "M0-DEEP-v1"
    out.mkdir(parents=True, exist_ok=False)
    md = r.compile_model([r.midpoint()], "midpoint", "S2")
    baseline_path = r.RUN / "M0-R1" / "solution.csv"
    base = r.start_from_csv(md, baseline_path)
    base_profit = profit(md, base)
    base_acts = activations(md, base)

    v1, a = solve_custom(md, 300, base, gap=0.001)
    if not a["solution_valid"]:
        raise RuntimeError("W1 stage 1 produced no feasible solution")
    p1 = profit(md, v1)
    floor = 0.999 * max(base_profit, p1)
    writecsv(out / "candidate_stage1.csv", rows_from_vals(md, v1, "M0-DEEP-stage1"))
    dump(out / "stage1_solver.json", a)

    costs = np.zeros(len(md.meta))
    for j in md.z.values():
        costs[j] = 1.0
    v2, b = solve_custom(
        md,
        120,
        v1,
        costs=costs,
        extra_rows=[(md.profit_coefs[0], floor, INF)],
        gap=0.001,
    )
    if not b["solution_valid"]:
        raise RuntimeError("W1 stage 2 produced no feasible solution")
    cap = activations(md, v2)
    writecsv(out / "candidate_stage2.csv", rows_from_vals(md, v2, "M0-DEEP-stage2"))
    dump(out / "stage2_solver.json", b)

    activation_row = {j: 1.0 for j in md.z.values()}
    v3, c = solve_custom(
        md,
        60,
        v2,
        costs=np.asarray(md.obj, dtype=float),
        extra_rows=[(md.profit_coefs[0], floor, INF), (activation_row, cap, cap)],
        gap=0.001,
    )
    dump(out / "stage3_solver.json", c)
    if c["solution_valid"]:
        writecsv(out / "candidate_stage3.csv", rows_from_vals(md, v3, "M0-DEEP-stage3"))

    candidates = [("M0-R1", base, base_profit, base_acts), ("stage1", v1, p1, activations(md, v1))]
    if c["solution_valid"]:
        candidates.append(("stage3", v3, profit(md, v3), activations(md, v3)))
    best_profit = max(x[2] for x in candidates)
    near = [x for x in candidates if x[2] >= 0.999 * best_profit]
    chosen = min(near, key=lambda x: (x[3], -x[2], x[0]))
    writecsv(out / "solution.csv", rows_from_vals(md, chosen[1], "M0-DEEP-v1"))
    record = {
        "protocol": "Q2-DEEPEN-v1",
        "authorization": "U015",
        "candidate": "M0-DEEP-v1",
        "baseline": {"run_id": "M0-R1", "profit": base_profit, "activations": base_acts},
        "stage1": {**a, "profit": p1, "activations": activations(md, v1)},
        "stage2": {**b, "profit_floor": floor, "activations": cap},
        "stage3": {**c, "profit": profit(md, v3) if c["solution_valid"] else None, "activations": activations(md, v3) if c["solution_valid"] else None},
        "selected_stage": chosen[0],
        "selected_profit": chosen[2],
        "selected_activations": chosen[3],
        "selection_rule": "within 0.1% of best independently reconstructable model profit, prefer fewer activations",
        "optimality_claim": "Only as supported by recorded status, bound and gap.",
    }
    dump(out / "solver.json", record)
    return record


def pick(rng, values, weights=(0.25, 0.50, 0.25)):
    return rng.choices(values, weights=weights, k=1)[0]


def random_set(label, count, seed):
    rng = random.Random(seed)
    rows = []
    for number in range(count):
        sid = f"{label}-{number + 1:03d}"
        wheat_factor = 1.0
        fungi_factor = {c: 1.0 for c, row in r.crops.items() if "食用菌" in row["crop_type"]}
        for year in YEARS:
            wheat_rate = pick(rng, [0.05, 0.075, 0.10])
            wheat_factor *= 1 + wheat_rate
            for crop, row in r.crops.items():
                other = pick(rng, [0.95, 1.0, 1.05])
                ym = pick(rng, [0.9, 1.0, 1.1])
                dm = wheat_factor if crop in (6, 7) else other
                step = year - 2023
                if "粮食" in row["crop_type"]:
                    pm = 1.0
                elif "蔬菜" in row["crop_type"]:
                    pm = 1.05**step
                elif row["crop_name"] == "羊肚菌":
                    pm = 0.95**step
                else:
                    decline = pick(rng, [0.01, 0.03, 0.05])
                    fungi_factor[crop] *= 1 - decline
                    pm = fungi_factor[crop]
                rows.append({
                    "scenario_set": label,
                    "scenario_id": sid,
                    "year": year,
                    "crop_id": crop,
                    "crop_name": row["crop_name"],
                    "demand_multiplier": f"{dm:.12g}",
                    "yield_multiplier": f"{ym:.12g}",
                    "cost_multiplier": f"{1.05**step:.12g}",
                    "price_multiplier": f"{pm:.12g}",
                    "wheat_corn_growth_rate": f"{wheat_rate:.12g}" if crop in (6, 7) else "",
                    "assumption_status": "model_scenario_not_forecast",
                })
    return rows


def level(u, weights, values):
    if u < weights[0]:
        return values[0]
    if u < weights[0] + weights[1]:
        return values[1]
    return values[2]


def sensitivity_sets(count=240, seed=20241207):
    rng = random.Random(seed)
    configs = {"midpoint_heavy": (0.10, 0.80, 0.10), "endpoint_heavy": (0.40, 0.20, 0.40)}
    all_rows = {name: [] for name in configs}
    for number in range(count):
        wf = {name: 1.0 for name in configs}
        fungi = {name: {c: 1.0 for c, row in r.crops.items() if "食用菌" in row["crop_type"]} for name in configs}
        for year in YEARS:
            u_wheat = rng.random()
            u_by_crop = {}
            for crop, row in r.crops.items():
                u_by_crop[crop] = (rng.random(), rng.random(), rng.random() if "食用菌" in row["crop_type"] and row["crop_name"] != "羊肚菌" else None)
            for name, weights in configs.items():
                wheat_rate = level(u_wheat, weights, [0.05, 0.075, 0.10])
                wf[name] *= 1 + wheat_rate
                for crop, row in r.crops.items():
                    u_other, u_yield, u_fungi = u_by_crop[crop]
                    other = level(u_other, weights, [0.95, 1.0, 1.05])
                    ym = level(u_yield, weights, [0.9, 1.0, 1.1])
                    dm = wf[name] if crop in (6, 7) else other
                    step = year - 2023
                    if "粮食" in row["crop_type"]:
                        pm = 1.0
                    elif "蔬菜" in row["crop_type"]:
                        pm = 1.05**step
                    elif row["crop_name"] == "羊肚菌":
                        pm = 0.95**step
                    else:
                        decline = level(u_fungi, weights, [0.01, 0.03, 0.05])
                        fungi[name][crop] *= 1 - decline
                        pm = fungi[name][crop]
                    all_rows[name].append({
                        "scenario_set": name,
                        "scenario_id": f"{name}-{number + 1:03d}",
                        "year": year,
                        "crop_id": crop,
                        "crop_name": row["crop_name"],
                        "demand_multiplier": f"{dm:.12g}",
                        "yield_multiplier": f"{ym:.12g}",
                        "cost_multiplier": f"{1.05**step:.12g}",
                        "price_multiplier": f"{pm:.12g}",
                        "wheat_corn_growth_rate": f"{wheat_rate:.12g}" if crop in (6, 7) else "",
                        "assumption_status": "sensitivity_not_forecast",
                    })
    return all_rows


def main():
    state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
    protocol = json.loads((Q / "protocols/deepen_v1.json").read_text(encoding="utf-8"))
    assert state["stage"] == "DEEPEN" and any(a["id"] == "U015" for a in state["authorizations"])
    assert protocol["budget_minutes"]["total_wall"] == 25
    assert all(sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())
    assert all(sha(ROOT / p) == h for p, h in state["questions"]["Q1"]["snapshots"]["Q1-D-v2-candidate"].items())
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError("Q2 deep output exists; refusing overwrite")
    OUT.mkdir(exist_ok=True)
    dump(OUT / "batch.json", {
        "protocol": "Q2-DEEPEN-v1",
        "authorization": "U015",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runner_sha256": sha(Path(__file__)),
        "source_hashes": state["data_snapshots"]["G1-v1-base"],
    })
    began = time.perf_counter()
    w1 = run_w1()
    SCEN.mkdir()
    holdout = random_set("holdout", 500, 20241107)
    writecsv(SCEN / "holdout_drivers.csv", holdout)
    sens = sensitivity_sets()
    writecsv(SCEN / "sensitivity_midpoint_heavy.csv", sens["midpoint_heavy"])
    writecsv(SCEN / "sensitivity_endpoint_heavy.csv", sens["endpoint_heavy"])
    elapsed = time.perf_counter() - began
    dump(OUT / "generation_complete.json", {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": elapsed,
        "wall_minutes": elapsed / 60,
        "holdout": {"count": 500, "seed": 20241107, "opened": True},
        "sensitivity": {"count_each": 240, "common_uniform_seed": 20241207},
        "w1_selected_stage": w1["selected_stage"],
    })
    print(json.dumps({"wall_minutes": elapsed / 60, "w1": w1["selected_stage"], "holdout": 500, "sensitivity_each": 240}, ensure_ascii=False))


if __name__ == "__main__":
    main()
