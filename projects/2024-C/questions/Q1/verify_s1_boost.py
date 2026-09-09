"""Independent verifier for U010 Q1-S1-BOOST-v1; imports no solver code."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal
import csv, hashlib, itertools, json

ROOT = Path(__file__).resolve().parents[2]
Q = Path(__file__).resolve().parent
D = ROOT / "data/frozen/G1-v1-base"
RUN = Q / "runs"
DEEP = Q / "deep_runs"
BOOST = Q / "boost_runs"
YEARS = range(2024, 2031)
EPS = Decimal(".00002")


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def dec(value): return Decimal(str(value))
def readcsv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
def dump(path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def writecsv(path, rows):
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
assert state["stage"] == "DEEPEN"
assert any(a["id"] == "U010" and a["plan_version"] == "Q1-S1-BOOST-v1" for a in state["authorizations"])
assert all(sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())

lands = {r["land_id"]: r for r in readcsv(D / "lands.csv")}
crops = {int(r["crop_id"]): r for r in readcsv(D / "crops.csv")}
params = {(int(r["crop_id"]), r["land_type"], r["season"]): r for r in readcsv(D / "parameters_effective.csv")}
hist = readcsv(D / "planting_2023.csv")
prod2023 = readcsv(D / "production_2023.csv")
beans = {c for c, row in crops.items() if row["is_legume"] == "true"}
base = {(int(r["crop_id"]), r["season"]): dec(r["production_estimate_jin"]) for r in prod2023}
seasons, price_sets = defaultdict(set), defaultdict(set)
for c, lt, season in params:
    seasons[c].add(season)
    price_sets[(c, season)].add(dec(params[(c, lt, season)]["price_midpoint_candidate_yuan_per_jin"]))
assert all(len(v) == 1 for v in price_sets.values())
prices = {k: next(iter(v)) for k, v in price_sets.items()}
demands = {}
for sid, frac in (("D0", Decimal(0)), ("D05", Decimal(".05")), ("D10", Decimal(".10"))):
    values = dict(base)
    for crop, crop_seasons in seasons.items():
        observed = [s for s in crop_seasons if (crop, s) in base]
        missing = [s for s in crop_seasons if (crop, s) not in base]
        if frac and len(observed) == len(missing) == 1:
            total = base[(crop, observed[0])]
            values[(crop, observed[0])] = total * (1 - frac)
            values[(crop, missing[0])] = total * frac
        else:
            for season in missing: values[(crop, season)] = Decimal(0)
    demands[sid] = values

rank = {"单季": 0, "第一季": 1, "第二季": 2}
hist_rows, hist_bean, last = defaultdict(list), defaultdict(Decimal), defaultdict(set)
for row in hist:
    lid, crop = row["land_id"], int(row["crop_id"])
    hist_rows[lid].append(row)
    if crop in beans: hist_bean[lid] += dec(row["area_mu"])
for lid, rows in hist_rows.items():
    max_rank = max(rank[r["season"]] for r in rows)
    last[lid] = {int(r["crop_id"]) for r in rows if rank[r["season"]] == max_rank}


def calculate(rows, sid):
    production, cost = defaultdict(Decimal), Decimal(0)
    for row in rows:
        crop, year, season, area = int(row["crop_id"]), int(row["year"]), row["season"], dec(row["area_mu"])
        p = params[(crop, lands[row["land_id"]]["land_type"], season)]
        production[(crop, year, season)] += area * dec(p["yield_jin_per_mu"])
        cost += area * dec(p["cost_yuan_per_mu"])
    revenue = sum((prices[(c, s)] * min(q, demands[sid][(c, s)]) for (c, y, s), q in production.items()), Decimal(0))
    return revenue - cost, revenue, cost


def verify(path, sid):
    rows = readcsv(path)
    areas, bean_area, keys, local = defaultdict(Decimal), defaultdict(Decimal), set(), []
    for row in rows:
        lid, year, season, crop, area = row["land_id"], int(row["year"]), row["season"], int(row["crop_id"]), dec(row["area_mu"])
        lt, key = lands[lid]["land_type"], (lid, year, season, crop)
        if key in keys: local.append(("duplicate", key))
        keys.add(key)
        if year not in YEARS or (crop, lt, season) not in params: local.append(("bad_key", key)); continue
        land_area = dec(lands[lid]["area_mu"])
        if area + EPS < Decimal(".5") * land_area or area - land_area > EPS: local.append(("area_link", key, area))
        p = params[(crop, lt, season)]
        if dec(row["yield_jin_per_mu"]) != dec(p["yield_jin_per_mu"]) or dec(row["cost_yuan_per_mu"]) != dec(p["cost_yuan_per_mu"]) or dec(row["price_yuan_per_jin"]) != prices[(crop, season)]:
            local.append(("parameter_copy", key))
        areas[(lid, year, season)] += area
        if crop in beans: bean_area[(lid, year, season)] += area
    for lid, land in lands.items():
        land_area, lt = dec(land["area_mu"]), land["land_type"]
        for year in YEARS:
            if lt in ("平旱地", "梯田", "山坡地"):
                if abs(areas[(lid, year, "单季")] - land_area) > EPS: local.append(("capacity", lid, year))
            elif lt == "水浇地":
                a = tuple(areas[(lid, year, s)] for s in ("单季", "第一季", "第二季"))
                if not ((abs(a[0]-land_area)<=EPS and a[1]==a[2]==0) or (a[0]==0 and abs(a[1]-land_area)<=EPS and abs(a[2]-land_area)<=EPS)):
                    local.append(("water_mode", lid, year, a))
            elif abs(areas[(lid, year, "第一季")]-land_area)>EPS or abs(areas[(lid, year, "第二季")]-land_area)>EPS:
                local.append(("capacity", lid, year))
    plot_counts = Counter((c, y, s) for lid, y, s, c in keys)
    if plot_counts and max(plot_counts.values()) > 7: local.append(("plot_cap", max(plot_counts.values())))
    byslot = defaultdict(set)
    for lid, year, season, crop in keys: byslot[(lid, year, season)].add(crop)
    for lid, land in lands.items():
        previous, lt = set(last[lid]), land["land_type"]
        for year in YEARS:
            order = ["单季"] if lt in ("平旱地", "梯田", "山坡地") else (["单季"] if lt == "水浇地" and areas[(lid, year, "单季")] > 0 else ["第一季", "第二季"])
            for season in order:
                current = byslot[(lid, year, season)]
                if previous & current: local.append(("rotation", lid, year, season, sorted(previous & current)))
                previous = current
    for lid, land in lands.items():
        land_area = dec(land["area_mu"])
        for end in range(2025, 2031):
            total = (hist_bean[lid] if end == 2025 else Decimal(0)) + sum((bean_area[(lid, y, s)] for y in range(max(2024, end-2), end+1) for s in ("单季", "第一季", "第二季")), Decimal(0))
            if total + EPS < land_area: local.append(("bean_window", lid, end, total, land_area))
    profit, revenue, cost = calculate(rows, sid)
    solver = json.loads((path.parent / "solver.json").read_text(encoding="utf-8"))
    if abs(dec(solver["model_accounting_profit"]) - profit) > Decimal(".1"): local.append(("accounting", solver["model_accounting_profit"], profit))
    return {"scenario": sid, "profit_yuan": str(profit), "revenue_yuan": str(revenue), "cost_yuan": str(cost),
            "activations": len(keys), "max_plots": max(plot_counts.values()), "violations": [str(x) for x in local], "valid": not local}, rows


manifest = json.loads((DEEP / "manifest.json").read_text(encoding="utf-8"))["files"]
locked = {rel: expected for rel, expected in manifest.items()
          if "M1R3-D05-S1" in rel or "-S2" in rel or "result1_2_Q1-DRAFT-v1.xlsx" in rel}
locked_checks = [{"path": rel, "expected": expected, "actual": sha(Q / rel), "unchanged": sha(Q / rel) == expected} for rel, expected in locked.items()]

metrics, solutions = [], {}
for sid in ("D0", "D10"):
    metric, rows = verify(BOOST / f"BOOST-{sid}-S1" / "solution.csv", sid)
    solutions[sid] = rows
    old = calculate(readcsv(DEEP / f"M1R3-{sid}-S1" / "solution.csv"), sid)[0]
    m0 = calculate(readcsv(RUN / f"M0-{sid}-S1" / "solution.csv"), sid)[0]
    transfer = calculate(readcsv(DEEP / "M1R3-D05-S1" / "solution.csv"), sid)[0]
    metric.update({"M0_profit_yuan": str(m0), "old_M1R3_profit_yuan": str(old), "transferred_D05_profit_yuan": str(transfer),
                   "gain_vs_old_yuan": str(dec(metric["profit_yuan"])-old), "gain_vs_transfer_yuan": str(dec(metric["profit_yuan"])-transfer)})
    metrics.append(metric)
solutions["D05"] = readcsv(DEEP / "M1R3-D05-S1" / "solution.csv")

cross = []
for source in ("D0", "D05", "D10"):
    for target in ("D0", "D05", "D10"):
        p = calculate(solutions[source], target)[0]
        cross.append({"sale_case": "S1", "plan_source_scenario": source, "evaluation_scenario": target, "profit_yuan": f"{p:.6f}"})
for row in cross:
    best = max(dec(x["profit_yuan"]) for x in cross if x["evaluation_scenario"] == row["evaluation_scenario"])
    row["regret_vs_best_of_three_plans_yuan"] = f"{best-dec(row['profit_yuan']):.6f}"

similarity = []
for a, b in itertools.combinations(("D0", "D05", "D10"), 2):
    aa = {(r["land_id"], int(r["year"]), r["season"], int(r["crop_id"])): dec(r["area_mu"]) for r in solutions[a]}
    bb = {(r["land_id"], int(r["year"]), r["season"], int(r["crop_id"])): dec(r["area_mu"]) for r in solutions[b]}
    keys = set(aa) | set(bb); inter = set(aa) & set(bb)
    l1 = sum((abs(aa.get(k, 0)-bb.get(k, 0)) for k in keys), Decimal(0)); den = sum(aa.values(), Decimal(0))
    similarity.append({"sale_case": "S1", "scenario_a": a, "scenario_b": b, "area_l1_mu": f"{l1:.6f}",
                       "area_l1_share_of_plan_a_percent": f"{l1/den*100:.6f}", "activation_jaccard": f"{Decimal(len(inter))/Decimal(len(keys)):.6f}"})

writecsv(BOOST / "comparison.csv", metrics)
writecsv(BOOST / "cross_evaluation.csv", cross)
writecsv(BOOST / "scenario_similarity.csv", similarity)
validation = {"protocol": "Q1-S1-BOOST-v1", "authorization": "U010", "verifier_sha256": sha(Path(__file__)),
              "source_snapshot_valid": True, "locked_files_checked": len(locked_checks),
              "locked_files_unchanged": all(x["unchanged"] for x in locked_checks), "locked_checks": locked_checks,
              "target_results": metrics, "hard_constraint_violations": sum(len(x["violations"]) for x in metrics),
              "checks_passed": all(x["valid"] for x in metrics) and all(x["unchanged"] for x in locked_checks),
              "human_verification": "pending",
              "limitations": ["D0/D05/D10 are assumed demand allocations, not observed demand.", "Prices use midpoint candidates.", "Time-limited incumbents are not proven globally optimal."]}
dump(BOOST / "validation.json", validation)
print(json.dumps({"passed": validation["checks_passed"], "targets": metrics, "locked_files_checked": len(locked_checks)}, ensure_ascii=False, indent=2))
assert validation["checks_passed"]
