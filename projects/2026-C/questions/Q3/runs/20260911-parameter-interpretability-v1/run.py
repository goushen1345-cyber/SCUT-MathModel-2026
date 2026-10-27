"""Q3 structural parameter checks for history length and intraday block size."""
from pathlib import Path
import importlib.util, json, os, hashlib

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
os.environ["NUMEXPR_MAX_THREADS"] = "1"

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
P = R.parents[3]
OLD = P / "questions/Q3/runs/20260911-s2-deepening-v1"
spec = importlib.util.spec_from_file_location("q3deep", OLD / "deepen.py")
deep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deep)

O = R / "outputs"
O.mkdir(parents=True, exist_ok=True)
deep.R = R
deep.O = O
deep.budget = deep.Budget()
def budget_check():
    assert deep.budget.calls <= 37000, "LP budget exhausted"
    assert deep.budget.elapsed + __import__("time").perf_counter() - deep.budget.start <= 1800, "research time budget exhausted"
deep.budget.check = budget_check


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_margin(history_days, block_hours, q=0.65, beta=0.7):
    if q == 0.65 and beta == 0.7:
        filename = f"w{history_days:02d}_h{block_hours:02d}.npz"
    else:
        filename = f"q{int(round(q*100)):02d}_b{int(round(beta*100)):03d}_w{history_days:02d}_h{block_hours:02d}.npz"
    path = O / "margins" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return np.load(path)["values"]

    old = dict(np.load(deep.BASE / "outputs/error_records.npz"))
    rr, tt, ee, tag = old["release"], old["target"], old["error"], old["kind"]
    releases = np.load(deep.BASE / "outputs/sources.npz")["release"]
    slots_per_block = block_hours * 6
    groups = 24 // block_hours
    source_group = tt % 144 // slots_per_block
    values = np.full((1460, 288), np.nan)
    meta = []

    for b, release in enumerate(releases):
        causal = (
            (rr >= release - history_days * 144)
            & (rr < release)
            & (tt + 1 <= release)
            & (rr % 144 == release % 144)
        )
        n = 288 - release % 144
        target = release + np.arange(n)
        future_kind = (np.arange(n) >= 144).astype(int)
        for kind in (0, 1):
            same_kind = causal & (tag == kind)
            for group in range(groups):
                destination = (target % 144 // slots_per_block == group) & (future_kind == kind)
                if not destination.any():
                    continue
                use = same_kind & (source_group == group)
                fallback = 0
                if use.sum() < 24:
                    use = same_kind
                    fallback = 1
                ids = np.flatnonzero(use)
                ids = ids[np.argsort(ee[ids], kind="stable")]
                if len(ids) >= 24:
                    ages = (release - 1) // 144 - tt[ids] // 144
                    value = deep.exact_quantile(ee[ids], ages, q, beta)
                else:
                    value = 0.0
                values[b, :n][destination] = value
                meta.append([b, kind, group, len(ids), fallback])
    np.savez_compressed(path, values=values, meta=np.asarray(meta, dtype=float))
    return values


def main():
    existing = json.loads((OLD / "analysis/summary.json").read_text(encoding="utf-8"))["selected"]
    rows = [dict(existing, history_days=28, block_hours=4, source="reused_verified_result")]
    cases = ((14, 4), (56, 4), (28, 1), (28, 2), (28, 3), (28, 6), (14, 2), (56, 2))
    for history_days, block_hours in cases:
        label = f"M_q65_b070_w{history_days:02d}_h{block_hours:02d}"
        result = deep.run(label, build_margin(history_days, block_hours), family="structure_sensitivity")
        result.update(history_days=history_days, block_hours=block_hours, q=0.65, beta=0.7, source="new_run")
        rows.append(result)

    tuning_cases = [(q, 0.7) for q in (0.60, 0.70, 0.75, 0.80)] + [(0.65, beta) for beta in (0.8, 1.0)]
    for q, beta in tuning_cases:
        label = f"M_q{int(round(q*100)):02d}_b{int(round(beta*100)):03d}_w28_h03"
        result = deep.run(label, build_margin(28, 3, q, beta), family="three_hour_parameter_recheck")
        result.update(history_days=28, block_hours=3, q=q, beta=beta, source="new_run")
        rows.append(result)

    refined_cases = [(q, 0.7) for q in (0.55, 0.575, 0.625)] + [(0.60, beta) for beta in (0.8, 1.0)]
    for q, beta in refined_cases:
        label = f"M_q{int(round(q*1000)):03d}_b{int(round(beta*100)):03d}_w28_h03"
        result = deep.run(label, build_margin(28, 3, q, beta), family="three_hour_parameter_refinement")
        result.update(history_days=28, block_hours=3, q=q, beta=beta, source="new_run")
        rows.append(result)

    final_margin = build_margin(28, 3, 0.60, 0.7)
    schedules = ((1, .75, .5, .25), (1, 1, .75, .5), (1, .5, 0, 0), (1, 0, 0, 0))
    for index, scale in enumerate(schedules, 1):
        label = f"FINAL_SCALE_{index}"
        result = deep.run(label, final_margin, scale=scale, family="final_release_scale_recheck")
        result.update(history_days=28, block_hours=3, q=.60, beta=.7, source="new_run")
        rows.append(result)
    for floor in (.25, .5, .75, 1.0):
        label = f"FINAL_FLOOR_{int(floor*100):03d}"
        result = deep.run(label, final_margin, floor=floor, family="final_order_floor_recheck")
        result.update(history_days=28, block_hours=3, q=.60, beta=.7, source="new_run")
        rows.append(result)

    frame = pd.DataFrame(rows).sort_values("total_cost")
    frame.to_csv(O / "comparison.csv", index=False, encoding="utf-8-sig", float_format="%.17g")
    winner = min(rows, key=lambda x: x["total_cost"])
    base = rows[0]
    summary = {
        "status": "completed_pending_saved_trace_recalculation",
        "baseline": base,
        "winner": winner,
        "comparisons": rows,
        "difference_from_28d_4h": {
            row["label"]: {
                "total_cost": row["total_cost"] - base["total_cost"],
                "ordinary_cost": row["ordinary_cost"] - base["ordinary_cost"],
                "emergency_cost": row["emergency_cost"] - base["emergency_cost"],
                "emergency_kwh": row["emergency_kwh"] - base["emergency_kwh"],
                "unused_order_kwh": row["unused_order_kwh"] - base["unused_order_kwh"]
            }
            for row in rows[1:]
        },
        "selection_boundary": "同一334天上的结构敏感性，不构成跨年独立验证",
        "lp_calls": deep.budget.calls,
        "protocol_sha256": sha(R / "protocol.json"),
        "code_sha256": sha(__file__)
    }
    dump(O / "summary.json", summary)
    deep.budget.save()
    print(json.dumps({"winner": winner["label"], "cost": winner["total_cost"], "lp_calls": deep.budget.calls}, ensure_ascii=False))


if __name__ == "__main__":
    main()
