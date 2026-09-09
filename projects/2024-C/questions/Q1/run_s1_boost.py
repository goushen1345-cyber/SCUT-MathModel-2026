"""Execute only the U010-approved Q1-S1-BOOST-v1 solver work."""
from pathlib import Path
from datetime import datetime, timezone
import json, shutil, time
import numpy as np
import run_trials as r
from run_deepen import start_from_csv, canonicalize_sales

ROOT = r.ROOT
Q = r.QDIR
OUT = Q / "boost_runs"
PROTOCOL = Q / "protocols" / "s1_boost_v1.json"
TRANSFER = Q / "deep_runs" / "M1R3-D05-S1" / "solution.csv"


def materialize(md, vals, path, label, sid):
    vals = canonicalize_sales(md, vals, sid)
    r.write_csv(path, r.solution_rows(md, vals, label, sid, "S1"))
    return vals, r.evaluate_csv(path, sid, "S1")


def solve_target(sid):
    out = OUT / f"BOOST-{sid}-S1"
    out.mkdir(parents=True, exist_ok=False)
    candidates = []

    transfer_copy = out / "candidate_transfer.csv"
    shutil.copyfile(TRANSFER, transfer_copy)
    transfer_eval = r.evaluate_csv(transfer_copy, sid, "S1")
    candidates.append(("transferred_D05", transfer_copy, transfer_eval))

    m1 = r.compile_model(sid, "S1", .5, 7, "profit")
    warm = start_from_csv(m1, TRANSFER, sid)
    _, v1, a = r.solve(m1, 180, gap=.01, start_values=warm)
    r.dump(out / "stage1_solver.json", a)
    if not a["solution_valid"]:
        raise RuntimeError(f"No stage-1 solution for {sid}")
    v1, ev1 = materialize(m1, v1, out / "candidate_stage1.csv", "BOOST-STAGE1", sid)
    candidates.append(("stage1", out / "candidate_stage1.csv", ev1))

    economic_best = max(transfer_eval["profit"], ev1["profit"])
    floor = economic_best * .999
    m2 = r.compile_model(sid, "S1", .5, 7, "management", profit_floor=floor)
    warm2 = start_from_csv(m2, out / "candidate_stage1.csv", sid)
    _, v2, b = r.solve(m2, 60, gap=.005, start_values=warm2)
    r.dump(out / "stage2_solver.json", b)
    activation_cap = None
    c = {"status": "SKIPPED_NO_STAGE2_SOLUTION", "solution_valid": False}
    if b["solution_valid"]:
        v2, ev2 = materialize(m2, v2, out / "candidate_stage2.csv", "BOOST-STAGE2", sid)
        candidates.append(("stage2", out / "candidate_stage2.csv", ev2))
        activation_cap = int(sum(v2[j] > .5 for j in m2.z.values()))
        m3 = r.compile_model(sid, "S1", .5, 7, "profit", profit_floor=floor,
                             activation_cap=activation_cap)
        warm3 = start_from_csv(m3, out / "candidate_stage2.csv", sid)
        _, v3, c = r.solve(m3, 45, gap=.005, start_values=warm3)
        r.dump(out / "stage3_solver.json", c)
        if c["solution_valid"]:
            v3, ev3 = materialize(m3, v3, out / "candidate_stage3.csv", "BOOST-STAGE3", sid)
            candidates.append(("stage3", out / "candidate_stage3.csv", ev3))
    else:
        r.dump(out / "stage3_solver.json", c)

    max_profit = max(ev["profit"] for _, _, ev in candidates)
    eligible = [x for x in candidates if x[2]["profit"] + max_profit * .001 + .1 >= max_profit]
    selected = min(eligible, key=lambda x: (x[2]["activations"], -x[2]["profit"], x[0]))
    name, src, ev = selected
    shutil.copyfile(src, out / "solution.csv")
    model_profit = ev["profit"]
    record = {
        "protocol": "Q1-S1-BOOST-v1", "authorization": "U010",
        "candidate": "M1R3-S1-BOOST", "scenario": sid, "sale_case": "S1",
        "alpha": .5, "cap": 7, "seed": r.SEED,
        "source_incumbent": "M1R3-D05-S1", "source_incumbent_target_profit": transfer_eval["profit"],
        "profit_floor": floor, "activation_cap_from_stage2": activation_cap,
        "stage1": a, "stage2": b, "stage3": c, "selected_stage": name,
        "candidate_metrics": [{"stage": n, **e} for n, _, e in candidates],
        "selected_profit": ev["profit"], "selected_revenue": ev["revenue"],
        "selected_cost": ev["cost"], "selected_activations": ev["activations"],
        "model_accounting_profit": model_profit, "accounting_difference": 0.0,
        "time_limits_seconds": [180, 60, 45],
        "selection_rule": "Among candidates within 0.1% of maximum independently recomputed profit, minimize activations; then maximize profit.",
        "optimality_claim": "Time-limited incumbent only; use recorded bound and gap.",
    }
    r.dump(out / "solver.json", record)
    return {"run_id": out.name, "scenario": sid, "selected_stage": name,
            "profit": ev["profit"], "activations": ev["activations"],
            "transfer_profit": transfer_eval["profit"], "stage1_status": a["status"],
            "stage1_gap": a["mip_gap"], "stage2_status": b["status"], "stage3_status": c["status"]}


def main():
    state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert state["stage"] == "DEEPEN"
    assert any(a["id"] == "U010" and a["plan_version"] == "Q1-S1-BOOST-v1" for a in state["authorizations"])
    assert protocol["target_scenarios"] == ["D0", "D10"] and protocol["sale_case"] == "S1"
    assert all(r.sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())
    if OUT.exists():
        raise RuntimeError("boost_runs already exists; refusing to overwrite")
    OUT.mkdir()
    started = time.perf_counter()
    r.dump(OUT / "batch.json", {
        "protocol": "Q1-S1-BOOST-v1", "authorization": "U010",
        "started_utc": datetime.now(timezone.utc).isoformat(), "seed": r.SEED,
        "data_version": "G1-v1-base", "source_hashes": state["data_snapshots"]["G1-v1-base"],
        "runner_sha256": r.sha(Path(__file__)), "locked_manifest_sha256": r.sha(Q / "deep_runs/manifest.json")})
    rows = [solve_target(sid) for sid in ("D0", "D10")]
    elapsed = time.perf_counter() - started
    r.write_csv(OUT / "solver_run_index.csv", rows)
    r.dump(OUT / "solver_batch_complete.json", {
        "finished_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": elapsed,
        "wall_minutes": elapsed / 60, "completed": len(rows), "solver_budget_minutes": 9.5})
    print(json.dumps({"completed": len(rows), "wall_minutes": elapsed / 60, "results": rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
