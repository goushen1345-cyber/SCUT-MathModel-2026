"""Generate only the U018-approved Q3 relationship graph and trial scenarios."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import csv, hashlib, json, math, random, statistics

ROOT = Path(__file__).resolve().parents[2]
Q = Path(__file__).resolve().parent
DATA = ROOT / "data/frozen/G1-v1-base"
OUT = Q / "runs/scenarios"
YEARS = list(range(2024, 2031))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readcsv(p):
    with p.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def writecsv(p, rows):
    rows = list(rows)
    with p.open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def dump(p, obj): p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def cdf(z): return .5 * (1 + math.erf(z / math.sqrt(2)))
def level(z, values):
    u = cdf(z)
    return values[0] if u < .25 else values[1] if u < .75 else values[2]
def corr(xs, ys):
    if len(xs) < 2 or statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0: return None
    return statistics.correlation(xs, ys)
def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i]); out = [0.0] * len(values); pos = 0
    while pos < len(order):
        end = pos + 1
        while end < len(order) and values[order[end]] == values[order[pos]]: end += 1
        rank = (pos + end - 1) / 2
        for j in order[pos:end]: out[j] = rank
        pos = end
    return out

state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
assert state["stage"] == "DEEPEN" and state["active_question"] == "Q3"
assert any(a["id"] == "U020" and a["plan_version"] == "Q3-DEEPEN-v1" for a in state["authorizations"])
assert all(sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())
for qn in ("Q1", "Q2"):
    q = state["questions"][qn]; snap = q["snapshots"][q["frozen_version"]]
    assert all(sha(ROOT / p) == h for p, h in snap.items())
protocol = json.loads((Q / "protocols/relationship_v1.json").read_text(encoding="utf-8"))
assert protocol["status"] == "PROPOSED_NOT_RUN" and protocol["sampling"]["reserved_future_holdout_samples"] == 500

crops = {int(r["crop_id"]): r for r in readcsv(DATA / "crops.csv")}
params = readcsv(DATA / "parameters_effective.csv")

# Crop-level synthetic graph.  A pool is the broad crop class plus its eligible-season signature.
agg = defaultdict(lambda: {"price": [], "yield": [], "cost": [], "seasons": set()})
for r in params:
    c = int(r["crop_id"]); a = agg[c]
    a["price"].append(float(r["price_midpoint_candidate_yuan_per_jin"]))
    a["yield"].append(float(r["yield_jin_per_mu"]))
    a["cost"].append(float(r["cost_yuan_per_mu"])); a["seasons"].add(r["season"])
def broad(ctype):
    if "粮食" in ctype: return "粮食"
    if "蔬菜" in ctype: return "蔬菜"
    return "食用菌"
features = {}
for c, a in agg.items():
    features[c] = {
        "price": statistics.fmean(a["price"]), "yield": statistics.fmean(a["yield"]),
        "cost": statistics.fmean(a["cost"]),
        "pool": broad(crops[c]["crop_type"]) + "|" + "/".join(sorted(a["seasons"])),
    }
zfeatures = {}
for pool in sorted({x["pool"] for x in features.values()}):
    ids = [c for c, x in features.items() if x["pool"] == pool]
    for key in ("price", "yield", "cost"):
        vals = [math.log(features[c][key]) for c in ids]; mu = statistics.fmean(vals); sd = statistics.pstdev(vals) or 1.0
        for c, value in zip(ids, vals): zfeatures.setdefault(c, {})[key] = (value - mu) / sd
edges = {}
for c, x in features.items():
    peers = [d for d, y in features.items() if d != c and y["pool"] == x["pool"]]
    distances = sorted((math.sqrt(sum((zfeatures[c][k] - zfeatures[d][k]) ** 2 for k in ("price", "yield", "cost"))), d) for d in peers)
    for rank_no, (distance, d) in enumerate(distances[:2], 1):
        pair = tuple(sorted((c, d)))
        old = edges.get(pair)
        if old is None or rank_no < old["rank"]: edges[pair] = {"rank": rank_no, "distance": distance}
neighbours = defaultdict(list); edge_rows = []
for (a, b), info in sorted(edges.items()):
    kind = "substitute" if info["rank"] == 1 else "complement"
    coef = .15 if kind == "substitute" else -.10
    neighbours[a].append((b, kind, coef)); neighbours[b].append((a, kind, coef))
    edge_rows.append({
        "crop_a": a, "crop_a_name": crops[a]["crop_name"], "crop_b": b, "crop_b_name": crops[b]["crop_name"],
        "sales_pool": features[a]["pool"], "edge_rank": info["rank"], "standardized_distance": f'{info["distance"]:.12g}',
        "RS_type": "substitute", "RS_coefficient": .15, "RSC_type": kind, "RSC_coefficient": coef,
        "assumption_status": "synthetic_not_observed",
    })

def normal(rng): return rng.gauss(0, 1)
def base_rows(label, count, seed):
    rng = random.Random(seed); rows = []
    for number in range(1, count + 1):
        sid = f"{label}-{number:03d}"
        grain_growth = 1.0; fungi_price = {c: 1.0 for c in crops if broad(crops[c]["crop_type"]) == "食用菌"}
        for year in YEARS:
            market = {g: normal(rng) for g in ("粮食", "蔬菜", "食用菌")}; inflation = normal(rng); weather = {g: normal(rng) for g in market}
            grain_rate = level(math.sqrt(.5) * market["粮食"] + math.sqrt(.5) * normal(rng), [.05, .075, .10]); grain_growth *= 1 + grain_rate
            for c, crop in crops.items():
                group = broad(crop["crop_type"]); zd = math.sqrt(.5) * market[group] + math.sqrt(.5) * normal(rng)
                zp = .495 * market[group] + .4 * inflation + math.sqrt(1 - .495**2 - .4**2) * normal(rng)
                zy = math.sqrt(.3) * weather[group] + math.sqrt(.7) * normal(rng)
                dm = grain_growth if c in (6, 7) else level(zd, [.95, 1.0, 1.05])
                ym = level(zy, [.9, 1.0, 1.1]); cost_rate = level(inflation, [.04, .05, .06]); costm = (1 + cost_rate) ** (year - 2023)
                if group == "粮食": pm = 1.0
                elif group == "蔬菜": pm = (1 + level(zp, [.04, .05, .06])) ** (year - 2023)
                elif crop["crop_name"] == "羊肚菌": pm = .95 ** (year - 2023)
                else:
                    decline = level(-zp, [.01, .03, .05]); fungi_price[c] *= 1 - decline; pm = fungi_price[c]
                rows.append({
                    "scenario_set": label, "underlying_id": sid, "year": year, "crop_id": c, "crop_name": crop["crop_name"], "crop_group": group,
                    "demand_multiplier_base": dm, "yield_multiplier": ym, "cost_multiplier": costm, "price_multiplier": pm,
                    "latent_demand": zd, "latent_price": zp, "latent_inflation": inflation, "latent_yield": zy,
                    "assumption_status": "model_scenario_not_forecast",
                })
    return rows

def reference_price(c, year):
    group = broad(crops[c]["crop_type"]); step = year - 2023
    if group == "粮食": return 1.0
    if group == "蔬菜": return 1.05 ** step
    if crops[c]["crop_name"] == "羊肚菌": return .95 ** step
    return .97 ** step

def expand_worlds(base):
    indexed = {(r["underlying_id"], r["year"], r["crop_id"]): r for r in base}; out = []
    for r in base:
        c = r["crop_id"]; year = r["year"]
        for world in ("R0", "RS", "RSC"):
            effect = 0.0
            if world != "R0":
                for neighbour, rsc_kind, rsc_coef in neighbours.get(c, []):
                    coef = .15 if world == "RS" else rsc_coef
                    nr = indexed[(r["underlying_id"], year, neighbour)]
                    relative_deviation = nr["price_multiplier"] / reference_price(neighbour, year) - 1
                    effect += coef * relative_deviation
            relationship_multiplier = min(1.10, max(.90, 1 + effect))
            out.append({
                "scenario_set": r["scenario_set"], "underlying_id": r["underlying_id"],
                "scenario_id": r["underlying_id"] + "-" + world, "relationship_world": world,
                "year": year, "crop_id": c, "crop_name": r["crop_name"], "crop_group": r["crop_group"],
                "demand_multiplier": f'{r["demand_multiplier_base"] * relationship_multiplier:.12g}',
                "demand_multiplier_base": f'{r["demand_multiplier_base"]:.12g}',
                "relationship_multiplier": f'{relationship_multiplier:.12g}',
                "yield_multiplier": f'{r["yield_multiplier"]:.12g}', "cost_multiplier": f'{r["cost_multiplier"]:.12g}',
                "price_multiplier": f'{r["price_multiplier"]:.12g}', "assumption_status": r["assumption_status"],
            })
    return out

def stress_rows():
    specs = [
        ("worst_all", .05, .95, .90, .06, .04, .05), ("low_demand", .05, .95, 1.0, .05, .05, .03),
        ("low_yield", .075, 1.0, .90, .05, .05, .03), ("high_cost", .075, 1.0, 1.0, .06, .05, .03),
        ("weak_prices", .075, 1.0, 1.0, .05, .04, .05), ("production_market", .05, .95, .90, .05, .04, .03),
    ]; base = []
    for name, grain_rate, other_demand, yield_m, cost_rate, veg_rate, fungi_decline in specs:
        grain_growth = 1.0; fungi_price = {c: 1.0 for c in crops if broad(crops[c]["crop_type"]) == "食用菌"}
        for year in YEARS:
            grain_growth *= 1 + grain_rate; step = year - 2023
            for c, crop in crops.items():
                group = broad(crop["crop_type"]); dm = grain_growth if c in (6, 7) else other_demand
                if group == "粮食": pm = 1.0
                elif group == "蔬菜": pm = (1 + veg_rate) ** step
                elif crop["crop_name"] == "羊肚菌": pm = .95 ** step
                else: fungi_price[c] *= 1 - fungi_decline; pm = fungi_price[c]
                base.append({
                    "scenario_set": "stress", "underlying_id": "stress-" + name, "year": year, "crop_id": c,
                    "crop_name": crop["crop_name"], "crop_group": group, "demand_multiplier_base": dm,
                    "yield_multiplier": yield_m, "cost_multiplier": (1 + cost_rate) ** step,
                    "price_multiplier": pm, "assumption_status": "named_stress_not_forecast",
                })
    return expand_worlds(base)

def spearman(xs, ys): return corr(ranks(xs), ranks(ys))

def dependence_audit(base):
    dp_x = [r["latent_demand"] for r in base]; dp_y = [r["latent_price"] for r in base]
    pc_x = [r["latent_price"] for r in base]; pc_y = [r["latent_inflation"] for r in base]
    by_key = defaultdict(dict)
    for r in base: by_key[(r["underlying_id"], r["year"], r["crop_group"])][r["crop_id"]] = r["latent_yield"]
    y1 = []; y2 = []
    for values in by_key.values():
        ids = sorted(values)
        for i in range(len(ids) - 1): y1.append(values[ids[i]]); y2.append(values[ids[i + 1]])
    return {
        "demand_price": {"target": .35, "pearson": corr(dp_x, dp_y), "spearman": spearman(dp_x, dp_y)},
        "price_cost": {"target": .40, "pearson": corr(pc_x, pc_y), "spearman": spearman(pc_x, pc_y)},
        "yield_within_group": {"target": .30, "pearson": corr(y1, y2), "spearman": spearman(y1, y2)},
    }

def main():
    state = json.loads((ROOT / "state/state.json").read_text(encoding="utf-8"))
    assert state["stage"] == "DEEPEN" and state["active_question"] == "Q3"
    assert any(a["id"] == "U020" and a["plan_version"] == "Q3-DEEPEN-v1" for a in state["authorizations"])
    assert all(sha(ROOT / p) == h for p, h in state["data_snapshots"]["G1-v1-base"].items())
    for question in ("Q1", "Q2"):
        q = state["questions"][question]
        assert all(sha(ROOT / p) == h for p, h in q["snapshots"][q["frozen_version"]].items())
    if OUT.exists(): raise RuntimeError("scenario output exists; refusing overwrite")
    OUT.mkdir(parents=True)
    training_base = base_rows("training", 120, 20250108); comparison_base = base_rows("comparison", 300, 20250208)
    training = expand_worlds(training_base); comparison = expand_worlds(comparison_base); stress = stress_rows()
    audit = dependence_audit(training_base)
    assert all(abs(v["pearson"] - v["target"]) <= .08 for v in audit.values()), audit
    assert all(row["crop_a"] != row["crop_b"] for row in edge_rows)
    assert all(.90 <= float(r["relationship_multiplier"]) <= 1.10 for r in training + comparison + stress)
    writecsv(OUT / "relationship_edges.csv", edge_rows)
    writecsv(OUT / "training_drivers.csv", training); writecsv(OUT / "comparison_drivers.csv", comparison); writecsv(OUT / "stress_drivers.csv", stress)
    validation = {
        "protocol": "Q3-RELATION-v1", "authorization": "U018", "created_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {"edges": len(edge_rows), "training_underlying": 120, "training_world_scenarios": 360, "comparison_underlying": 300, "comparison_world_scenarios": 900, "named_stress": 18},
        "dependence_audit": audit, "relationship_multiplier_range": [min(float(r["relationship_multiplier"]) for r in training + comparison + stress), max(float(r["relationship_multiplier"]) for r in training + comparison + stress)],
        "future_holdout_generated": False, "source_snapshots_valid": True, "passed": True, "human_verification": "pending",
    }
    dump(OUT / "validation.json", validation)
    print(json.dumps(validation, ensure_ascii=False))

if __name__ == "__main__": main()
