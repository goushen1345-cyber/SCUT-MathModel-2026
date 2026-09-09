import csv
import hashlib
import json
from pathlib import Path


project = Path(__file__).resolve().parents[1]
paper = project / "paper"
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
checks = []


def check(name, condition, detail):
    checks.append({"name": name, "passed": bool(condition), "detail": detail})


check(
    "all_questions_frozen_valid",
    all(q["status"] == "FROZEN" and q["validity"] == "VALID" for q in state["questions"].values()),
    {q: {"status": v["status"], "validity": v["validity"]} for q, v in state["questions"].items()},
)

for q_name, q in state["questions"].items():
    manifest = q["snapshots"][q["frozen_version"]]
    bad = []
    for rel, expected in manifest.items():
        path = project / rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            bad.append(rel)
    check(f"{q_name}_snapshot", not bad, {"files": len(manifest), "mismatches": bad})

with (paper / "evidence_matrix_v1.csv").open(encoding="utf-8-sig", newline="") as stream:
    evidence_rows = list(csv.DictReader(stream))
missing = []
for row in evidence_rows:
    for rel in (part.strip() for part in row["evidence"].split(";")):
        if not (project / rel).is_file():
            missing.append({"claim_id": row["claim_id"], "path": rel})
check("evidence_sources_exist", not missing, {"claims": len(evidence_rows), "missing": missing})

with (project / "questions/Q1/boost_runs/comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
    q1_boost = {r["scenario"]: r for r in csv.DictReader(stream)}
with (project / "questions/Q1/deep_runs/main_comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
    q1_main = {(r["scenario"], r["sale_case"]): r for r in csv.DictReader(stream)}
check(
    "q1_key_metrics",
    abs(float(q1_boost["D0"]["profit_yuan"]) - 39677985.875) < 0.01
    and int(q1_boost["D0"]["activations"]) == 738
    and abs(float(q1_main[("D0", "S2")]["M1R3_profit_yuan"]) - 61683124.375) < 0.01
    and int(q1_main[("D0", "S2")]["activations"]) == 662,
    "Q1 S1/S2 frozen D0 metrics",
)

with (project / "questions/Q2/deep_runs/holdout_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
    q2_summary = {r["candidate"]: r for r in csv.DictReader(stream) if r["demand_base"] == "D05" and r["sale_case"] == "S2"}
with (project / "questions/Q2/deep_runs/holdout_pairwise.csv").open(encoding="utf-8-sig", newline="") as stream:
    q2_pair = {(r["candidate"], r["reference"]): r for r in csv.DictReader(stream)}
check(
    "q2_key_metrics",
    abs(float(q2_summary["M0"]["mean"]) - 67173281.715915) < 0.01
    and abs(float(q2_summary["M0"]["worst10_mean"]) - 65618964.038876) < 0.01
    and int(q2_pair[("M0", "B0")]["positive"]) == 500
    and int(q2_pair[("M1", "M0")]["negative"]) == 121,
    "Q2 holdout and paired metrics",
)

with (project / "questions/Q3/deep_runs/holdout_summary.csv").open(encoding="utf-8-sig", newline="") as stream:
    q3_holdout = next(csv.DictReader(stream))
q3_validation = json.loads((project / "questions/Q3/deep_runs/validation.json").read_text(encoding="utf-8"))
n30 = next(x for x in q3_validation["accounting_checks"] if x["candidate"] == "N30")
check(
    "q3_key_metrics",
    abs(float(q3_holdout["mean"]) - 67272781.855569) < 0.01
    and abs(float(q3_holdout["worst10_mean"]) - 65375850.693010) < 0.01
    and n30["hamming_changes_from_B0"] == 40
    and n30["evidence_status"] == "EXCLUDED_WRONG_REFERENCE",
    "Q3 holdout metrics and N30 exclusion",
)

plan_text = (paper / "plan_v1.md").read_text(encoding="utf-8")
required_boundaries = ["销量", "价格中点", "合成假设", "全局最优", "严格整块豆类", "N30"]
check("limitations_present", all(x in plan_text for x in required_boundaries), required_boundaries)

result = {
    "plan_version": "PAPER-PLAN-v1",
    "method": "standard-library source and frozen-evidence cross-check; no model execution",
    "checks": checks,
    "passed": all(item["passed"] for item in checks),
    "full_draft_created": False,
    "new_experiments_run": False,
    "human_verification": "pending",
}
(paper / "plan_validation_v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if not result["passed"]:
    raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({"passed": True, "checks": len(checks), "claims": len(evidence_rows)}, ensure_ascii=False))
