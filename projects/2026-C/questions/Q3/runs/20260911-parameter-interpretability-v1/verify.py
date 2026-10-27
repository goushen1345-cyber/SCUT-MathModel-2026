"""Independent reconstruction of saved Q3 structural-sensitivity traces."""
from pathlib import Path
from decimal import Decimal, localcontext
from fractions import Fraction
import json, hashlib
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
P = R.parents[3]
O = R / "outputs"
BASE = P / "questions/Q3/runs/20260911-four-candidates-v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(name, actual, expected, tolerance=1e-7):
    a, b = np.asarray(actual), np.asarray(expected)
    assert np.array_equal(np.isnan(a), np.isnan(b)), (name, "NaN positions differ")
    mask = np.isfinite(a) & np.isfinite(b)
    error = float(np.max(np.abs(a[mask] - b[mask]))) if np.any(mask) else 0.0
    maxima[name] = max(maxima.get(name, 0.0), error)
    assert error <= tolerance, (name, error)


def D(value):
    return Decimal(str(float(value)))


def execute_one(load_kw, pv_kw, order, state):
    load, pv, order = float(load_kw / 6), float(pv_kw / 6), max(0.0, float(order))
    direct = min(load, pv)
    need, surplus, old = load - direct, pv - direct, state
    if need > order:
        discharge = min(need - order, 5000 / 6, max(0.0, 0.9 * (state - 1200)))
        emergency = max(0.0, need - order - discharge)
        grid_charge = pv_charge = 0.0
        received = order
    else:
        charge = min(surplus + order - need, 5000 / 6, max(0.0, (10800 - state) / 0.9))
        pv_charge = min(surplus, charge)
        grid_charge = charge - pv_charge
        discharge = emergency = 0.0
        received = need + grid_charge
    state = old + 0.9 * (grid_charge + pv_charge) - discharge / 0.9
    row = np.array([old, state, received, received-grid_charge, direct, grid_charge,
                    pv_charge, discharge, emergency, max(0.0, order-received),
                    max(0.0, surplus-pv_charge), load])
    return row, state


summary = read(O / "summary.json")
assert summary["protocol_sha256"] == sha(R / "protocol.json")
assert summary["code_sha256"] == sha(R / "run.py")
source = dict(np.load(BASE / "outputs/sources.npz"))
actual, price = source["actual"], source["price"]
maxima, counts = {}, {"strategies": 0, "actual_intervals": 0, "margin_groups": 0}

for record in summary["comparisons"]:
    if record["source"] == "reused_verified_result":
        continue
    trace = dict(np.load(R / record["trace"]))
    days, q0, versions, saved = trace["days"], trace["q0"], trace["versions"], trace["execution"]
    assert np.array_equal(days, np.arange(31, 365))
    close("q0", q0, versions[:, 0], 1e-12)
    for release, start in enumerate((0, 36, 72, 108)):
        if release:
            close("locked_prefix", versions[:, release, :start], versions[:, release-1, :start], 1e-12)

    state = float(record["initial"])
    total = Decimal(0)
    rebuilt_daily = []
    for day_index, day in enumerate(days):
        before = state
        rebuilt = np.empty((144, 12))
        for release, start in enumerate((0, 36, 72, 108)):
            close("decision_state", trace["decision_storage"][day_index, release], state, 1e-7)
            for slot in range(start, start + 36):
                row, state = execute_one(*actual[day * 144 + slot], versions[day_index, release, slot], state)
                rebuilt[slot] = row
        close("execution", rebuilt, saved[day_index], 1e-6)
        delta = versions[day_index, 3] - q0[day_index]
        with localcontext() as context:
            context.prec = 40
            ordinary = sum((D(price[k])*D(versions[day_index,3,k]) + Decimal(".5")*D(price[k])*abs(D(delta[k])) for k in range(144)), Decimal(0))
            emergency = sum((Decimal(5)*D(price[k])*D(rebuilt[k,8]) for k in range(144)), Decimal(0))
        rebuilt_daily.append([before, state, float(ordinary), float(emergency), float(ordinary+emergency),
                              float(versions[day_index,3].sum()), float(rebuilt[:,8].sum()),
                              float(rebuilt[:,9].sum()), float(rebuilt[:,10].sum()),
                              float(np.maximum(-delta,0).sum()), float(np.maximum(delta,0).sum())])
        total += ordinary + emergency
        counts["actual_intervals"] += 144
    frame = pd.read_csv(R / record["daily_csv"], float_precision="round_trip")
    columns = ["initial", "final", "ordinary_cost", "emergency_cost", "total_cost", "order_kwh",
               "emergency_kwh", "unused_order_kwh", "unused_pv_kwh", "reduced_kwh", "increased_kwh"]
    close("daily", frame[columns].to_numpy(), np.asarray(rebuilt_daily), 1e-6)
    close("period_cost", float(total), record["total_cost"], 1e-5)
    close("final_state", state, record["final"], 1e-7)
    solver = pd.read_csv(R / f'outputs/strategies/{record["label"]}.solver.csv')
    assert len(solver) == 1336 and solver.residual.max() < 1e-6 and solver.dual_gap.max() < 1e-4
    assert solver.simultaneous.sum() == 0
    counts["strategies"] += 1

# Rebuild the selected 28-day, three-hour margin without importing run.py.
errors = dict(np.load(BASE / "outputs/error_records.npz"))
rr, tt, ee, kind = errors["release"], errors["target"], errors["error"], errors["kind"]
releases = source["release"]
selected_record = min(summary["comparisons"], key=lambda row: row["total_cost"])
selected_q = float(selected_record["q"])
selected_beta = float(selected_record["beta"])
margin_name = f"q{int(round(selected_q*100)):02d}_b{int(round(selected_beta*100)):03d}_w28_h03.npz"
saved_margin = np.load(O / "margins" / margin_name)["values"]
rebuilt_margin = np.full_like(saved_margin, np.nan)
group = tt % 144 // 18
q, beta = Fraction(str(selected_q)), Fraction(str(selected_beta))
for batch, release in enumerate(releases):
    pool = (rr >= release-28*144) & (rr < release) & (tt+1 <= release) & (rr % 144 == release % 144)
    n = 288 - release % 144
    targets = release + np.arange(n)
    future = (np.arange(n) >= 144).astype(int)
    for forecast_kind in (0, 1):
        same = pool & (kind == forecast_kind)
        for block in range(8):
            destination = (targets % 144 // 18 == block) & (future == forecast_kind)
            if not destination.any():
                continue
            use = same & (group == block)
            if use.sum() < 24:
                use = same
            ids = np.flatnonzero(use)
            ids = ids[np.argsort(ee[ids], kind="stable")]
            if len(ids) < 24:
                value = 0.0
            else:
                ages = (release-1)//144 - tt[ids]//144
                maximum_age = int(ages.max())
                weights = [beta.numerator**int(age) * beta.denominator**(maximum_age-int(age)) for age in ages]
                total_weight, accumulated, index = sum(weights), 0, len(ids)-1
                for j, weight in enumerate(weights):
                    accumulated += weight
                    if accumulated*q.denominator >= q.numerator*total_weight:
                        index = j
                        break
                value = max(0.0, float(ee[ids[index]]))
                assert int(np.max(tt[ids]+1)) <= release
            rebuilt_margin[batch, :n][destination] = value
            counts["margin_groups"] += 1
close("selected_margin", rebuilt_margin, saved_margin, 1e-10)

winner = min(summary["comparisons"], key=lambda row: row["total_cost"])
assert summary["winner"]["label"] == winner["label"]
result = {
    "status": "checks_completed",
    "counts": counts,
    "max_errors": maxima,
    "new_lp_calls": 0,
    "new_fits": 0,
    "selected": winner["label"],
    "selected_cost": winner["total_cost"],
    "reviewer": "same AI, independent saved-trace reconstruction; not human approval",
    "code_sha256": sha(__file__)
}
(O / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
