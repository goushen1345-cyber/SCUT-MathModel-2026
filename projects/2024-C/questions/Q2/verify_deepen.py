"""Independent verification and fixed-plan evaluation for Q2-DEEPEN-v1."""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics
import types


Q = Path(__file__).resolve().parent
ROOT = Q.parents[1]
DEEP = Q / "deep_runs"
TRIAL = Q / "runs"


source_path = Q / "verify_trials.py"
source = source_path.read_text(encoding="utf-8")
source = source.replace("assert state['stage']=='TRIAL'", "assert state['stage']=='DEEPEN'")
source = source.split("names=('B0','M0','M1','M2','M3')", 1)[0]
v = types.ModuleType("q2_independent_trial_verifier_reuse")
v.__file__ = str(source_path)
exec(compile(source, str(source_path), "exec"), v.__dict__)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def writecsv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_scenarios(path):
    rows = v.readcsv(path)
    grouped = v.drivers(path)
    return rows, grouped


def validate_scenarios(rows, grouped, expected_count, label):
    issues = []
    expected_rows = expected_count * 7 * len(v.crops)
    if len(rows) != expected_rows:
        issues.append(f"row_count:{len(rows)}!={expected_rows}")
    if len(grouped) != expected_count:
        issues.append(f"scenario_count:{len(grouped)}!={expected_count}")
    for row in rows:
        crop = int(row["crop_id"])
        year = int(row["year"])
        dm = float(row["demand_multiplier"])
        ym = float(row["yield_multiplier"])
        cm = float(row["cost_multiplier"])
        pm = float(row["price_multiplier"])
        if year not in v.YEARS or crop not in v.crops:
            issues.append("bad_key")
            break
        if min(dm, ym, cm, pm) <= 0:
            issues.append("nonpositive_driver")
            break
        if min(abs(ym - x) for x in (0.9, 1.0, 1.1)) > 1e-10:
            issues.append("yield_outside_levels")
            break
        if abs(cm - 1.05 ** (year - 2023)) > 1e-9:
            issues.append("cost_path_mismatch")
            break
        if crop not in (6, 7) and min(abs(dm - x) for x in (0.95, 1.0, 1.05)) > 1e-10:
            issues.append("other_demand_outside_levels")
            break
    return {"label": label, "rows": len(rows), "scenarios": len(grouped), "issues": issues, "passed": not issues}


def paired_summary(a, b):
    diffs = [x - y for x, y in zip(a, b)]
    mean = statistics.fmean(diffs)
    se = statistics.stdev(diffs) / math.sqrt(len(diffs))
    return {
        "mean_difference_yuan": mean,
        "ci95_low_yuan": mean - 1.96 * se,
        "ci95_high_yuan": mean + 1.96 * se,
        "positive": sum(x > 0 for x in diffs),
        "equal": sum(x == 0 for x in diffs),
        "negative": sum(x < 0 for x in diffs),
        "min_difference_yuan": min(diffs),
        "max_difference_yuan": max(diffs),
        "interpretation": "Monte Carlo error under Q2-UNCERTAINTY-v1, not real-world confidence",
    }


def strict_bean(rows):
    bean = defaultdict(Decimal)
    for row in rows:
        if int(row["crop_id"]) in v.beans:
            bean[(row["land_id"], int(row["year"]), row["season"])] += v.dec(row["area_mu"])
    hist_slot = defaultdict(Decimal)
    for row in v.hist:
        if int(row["crop_id"]) in v.beans:
            hist_slot[(row["land_id"], row["season"])] += v.dec(row["area_mu"])
    hist_full = {lid: any(l == lid and abs(a - v.dec(v.lands[lid]["area_mu"])) <= v.EPS for (l, _), a in hist_slot.items()) for lid in v.lands}
    violations = []
    for lid in v.lands:
        area = v.dec(v.lands[lid]["area_mu"])
        for end in range(2025, 2031):
            ok = end == 2025 and hist_full[lid]
            for year in range(max(2024, end - 2), end + 1):
                ok = ok or any(bean[(lid, year, season)] + v.EPS >= area for season in ("单季", "第一季", "第二季"))
            if not ok:
                violations.append({"land_id": lid, "window_end": end})
    return {"passed": not violations, "violations": len(violations), "examples": violations[:20], "role": "diagnostic only"}


def altered_trend(scenarios, rate):
    out = {}
    for sid, drv in scenarios.items():
        out[sid] = {}
        for (crop, year), d in drv.items():
            x = dict(d)
            step = year - 2023
            x["cost_multiplier"] = Decimal(str(rate)) ** step
            if "蔬菜" in v.crops[crop]["crop_type"]:
                x["price_multiplier"] = Decimal(str(rate)) ** step
            out[sid][(crop, year)] = x
    return out


def contribution(rows, scenarios, sale):
    totals = defaultdict(lambda: defaultdict(Decimal))
    for drv in scenarios.values():
        production = defaultdict(Decimal)
        costs = defaultdict(Decimal)
        for row in rows:
            lid = row["land_id"]
            year = int(row["year"])
            season = row["season"]
            crop = int(row["crop_id"])
            area = v.dec(row["area_mu"])
            par = v.params[(crop, v.lands[lid]["land_type"], season)]
            d = drv[(crop, year)]
            production[(crop, year, season)] += area * v.dec(par["yield_jin_per_mu"]) * d["yield_multiplier"]
            costs[(crop, year)] += area * v.dec(par["cost_yuan_per_mu"]) * d["cost_multiplier"]
        for (crop, year, season), qty in production.items():
            d = drv[(crop, year)]
            cap = v.bases["D05"][(crop, season)] * d["demand_multiplier"]
            full = min(qty, cap)
            extra = qty - full
            price = v.prices[(crop, season)] * d["price_multiplier"]
            disc = Decimal(0) if sale == "S1" else Decimal(".5") * extra * price
            t = totals[(crop, year)]
            t["production"] += qty
            t["excess"] += extra
            t["full_revenue"] += full * price
            t["discounted_revenue"] += disc
        for key, cost in costs.items():
            totals[key]["cost"] += cost
    n = Decimal(len(scenarios))
    out = {}
    for key, t in totals.items():
        vals = {k: x / n for k, x in t.items()}
        vals["profit"] = vals["full_revenue"] + vals["discounted_revenue"] - vals["cost"]
        out[key] = vals
    return out


def main():
    state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
    assert state["stage"] == "DEEPEN" and any(a["id"] == "U015" for a in state["authorizations"])
    assert all(sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())
    assert all(sha(ROOT / p) == h for p, h in state["questions"]["Q1"]["snapshots"]["Q1-D-v2-candidate"].items())

    plan_paths = {"B0": TRIAL / "B0/solution.csv", "M0": DEEP / "M0-DEEP-v1/solution.csv", "M1": TRIAL / "M1-R1/solution.csv"}
    plans = {name: v.readcsv(path) for name, path in plan_paths.items()}
    constraints = [v.verify_plan(name, rows) for name, rows in plans.items()]
    if not all(x["valid"] for x in constraints):
        raise RuntimeError("Hard-constraint verification failed")

    hold_rows, holdout = load_scenarios(DEEP / "scenarios/holdout_drivers.csv")
    mid_rows, mid = load_scenarios(DEEP / "scenarios/sensitivity_midpoint_heavy.csv")
    end_rows, endpoint = load_scenarios(DEEP / "scenarios/sensitivity_endpoint_heavy.csv")
    scenario_checks = [validate_scenarios(hold_rows, holdout, 500, "holdout"), validate_scenarios(mid_rows, mid, 240, "midpoint_heavy"), validate_scenarios(end_rows, endpoint, 240, "endpoint_heavy")]
    assert all(x["passed"] for x in scenario_checks)
    old_ids = set(v.training) | set(v.comparison) | set(v.stress)
    new_ids = set(holdout) | set(mid) | set(endpoint)
    set_separation = not (old_ids & new_ids) and len(new_ids) == 980
    assert set_separation

    summaries = []
    primary_values = {}
    primary_metrics = {}
    for base in ("D05", "D0", "D10"):
        for sale in ("S2", "S1"):
            for name, rows in plans.items():
                vals = [float(v.profit(rows, drv, base, sale)) for drv in holdout.values()]
                met = v.metrics(vals)
                summaries.append({"candidate": name, "demand_base": base, "sale_case": sale, **{k: f"{x:.6f}" for k, x in met.items()}})
                if base == "D05" and sale == "S2":
                    primary_values[name] = vals
                    primary_metrics[name] = met
    writecsv(DEEP / "holdout_summary.csv", summaries)
    pairs = []
    for name, ref in (("M0", "B0"), ("M1", "M0")):
        pairs.append({"candidate": name, "reference": ref, **paired_summary(primary_values[name], primary_values[ref])})
    writecsv(DEEP / "holdout_pairwise.csv", pairs)

    m1m0 = next(x for x in pairs if x["candidate"] == "M1")
    m0 = primary_metrics["M0"]
    m1 = primary_metrics["M1"]
    s1_rows = [x for x in summaries if x["demand_base"] == "D05" and x["sale_case"] == "S1"]
    s1 = {x["candidate"]: x for x in s1_rows}
    mean_gain = (m1["mean"] - m0["mean"]) / m0["mean"]
    tail_gain = (m1["worst10_mean"] - m0["worst10_mean"]) / m0["worst10_mean"]
    s1_tail_change = (float(s1["M1"]["worst10_mean"]) - float(s1["M0"]["worst10_mean"])) / float(s1["M0"]["worst10_mean"])
    m1_eligible = mean_gain >= 0.001 and tail_gain >= 0.001 and m1m0["ci95_low_yuan"] > 0 and s1_tail_change >= -0.001
    selected = "M1-R1" if m1_eligible else "M0-R1"

    sensitivity = []
    for setting, scenarios in (("midpoint_heavy", mid), ("endpoint_heavy", endpoint)):
        for rate in (1.04, 1.05, 1.06):
            altered = altered_trend(scenarios, rate)
            for base in ("D05", "D0", "D10"):
                for sale in ("S2", "S1"):
                    for name, rows in plans.items():
                        vals = [float(v.profit(rows, drv, base, sale)) for drv in altered.values()]
                        met = v.metrics(vals)
                        sensitivity.append({"weight_setting": setting, "cost_vegetable_factor": f"{rate:.2f}", "demand_base": base, "sale_case": sale, "candidate": name, "mean_profit_yuan": f"{met['mean']:.6f}", "worst10_mean_yuan": f"{met['worst10_mean']:.6f}"})
    writecsv(DEEP / "sensitivity_summary.csv", sensitivity)

    contribution_rows = []
    reconciliation = []
    for sale in ("S2", "S1"):
        c0 = contribution(plans["M0"], holdout, sale)
        c1 = contribution(plans["M1"], holdout, sale)
        total = Decimal(0)
        for crop, year in sorted(set(c0) | set(c1)):
            a = c0.get((crop, year), defaultdict(Decimal))
            b = c1.get((crop, year), defaultdict(Decimal))
            row = {"sale_case": sale, "crop_id": crop, "crop_name": v.crops[crop]["crop_name"], "year": year}
            for key in ("production", "excess", "full_revenue", "discounted_revenue", "cost", "profit"):
                row[f"M0_{key}"] = str(a[key])
                row[f"M1_{key}"] = str(b[key])
                row[f"difference_{key}"] = str(b[key] - a[key])
            total += b["profit"] - a["profit"]
            contribution_rows.append(row)
        direct = statistics.fmean(float(v.profit(plans["M1"], d, "D05", sale) - v.profit(plans["M0"], d, "D05", sale)) for d in holdout.values())
        reconciliation.append({"sale_case": sale, "component_sum": str(total), "direct_mean_difference": f"{direct:.6f}", "difference": str(total - Decimal(str(direct))), "passed": abs(total - Decimal(str(direct))) <= Decimal(".1")})
    writecsv(DEEP / "contribution_difference.csv", contribution_rows)
    assert all(x["passed"] for x in reconciliation)

    bean = {name: strict_bean(rows) for name, rows in plans.items()}
    result = {
        "protocol": "Q2-DEEPEN-v1",
        "authorization": "U015",
        "method": "independent standard-library reconstruction; imports neither generator nor optimizer",
        "source_snapshots_valid": True,
        "scenario_checks": scenario_checks,
        "set_separation": set_separation,
        "scenario_hashes": {p.name: sha(p) for p in (DEEP / "scenarios").glob("*.csv")},
        "constraint_checks": constraints,
        "strict_bean_diagnostic": bean,
        "primary_metrics": primary_metrics,
        "holdout_pairwise": pairs,
        "m1_switch_tests": {"mean_gain": mean_gain, "worst10_gain": tail_gain, "paired_ci_low_positive": m1m0["ci95_low_yuan"] > 0, "s1_worst10_change": s1_tail_change, "eligible": m1_eligible},
        "selected_candidate": selected,
        "contribution_reconciliation": reconciliation,
        "passed": True,
        "human_verification": "pending",
        "limitations": ["Scenario probabilities are modeling assumptions, not estimates", "D05 demand uses a production proxy", "Strict whole-plot bean compliance is diagnostic", "MIP claims retain recorded gaps"],
    }
    dump(DEEP / "validation.json", result)
    dump(DEEP / "selection.json", {"selected_candidate": selected, "m1_eligible": m1_eligible, "rule": "pre-registered Q2-DEEPEN-v1 switch rule", "human_freeze": False})
    print(json.dumps({"selected": selected, "switch": result["m1_switch_tests"], "pairwise": pairs, "strict_bean": bean}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
