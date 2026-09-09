import hashlib
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
q3 = project / "questions/Q3"
version = "Q3-D-v1-candidate"

record = {
    "version": version,
    "authorization": "U021",
    "status": "FROZEN_BY_USER",
    "data_version": "G1-v1-base",
    "q2_reference": "Q2-D-v1-candidate",
    "selected_plan": "questions/Q3/runs/B0/solution.csv",
    "selected_plan_identity": "Q2 frozen M0-R1 plan evaluated as Q3 B0",
    "valid_local_comparators": ["N0", "N10"],
    "excluded_evidence": {
        "candidate": "N30",
        "reason": "Hamming constraint referenced N10 and produced 40 changes from B0, exceeding the approved limit of 30",
        "rerun": False,
    },
    "limitations": [
        "Relationship graph and coefficients are synthetic assumptions rather than estimates from the attachments.",
        "D05 normal sales use a production-based proxy because observed sales are unavailable.",
        "N30 is invalid for selection and was not rerun after holdout access.",
        "B0 is a validated time-limited feasible plan, not a proven global optimum.",
        "The aggregate bean-area rule does not prove strict whole-plot bean rotation coverage.",
    ],
    "human_verification": "User authorized freezing the named version with disclosed limitations; item-by-item manual recalculation is not claimed.",
    "paper_stage": "NOT_AUTHORIZED",
}
record_path = q3 / f"freeze_record_{version}.json"
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

files = []
for path in q3.rglob("*"):
    if not path.is_file():
        continue
    rel_q3 = path.relative_to(q3)
    if "__pycache__" in rel_q3.parts or path.suffix == ".pyc":
        continue
    if path.name.startswith("commit_") or path.name == "prepare_freeze_q3.py":
        continue
    if path.name == f"snapshot_{version}.json":
        continue
    files.append(path)
files.append(project / "paper_evidence/Q3.md")

snapshot = {}
for path in sorted(set(files), key=lambda p: p.relative_to(project).as_posix()):
    rel = path.relative_to(project).as_posix()
    snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

snapshot_doc = {"version": version, "files": snapshot}
snapshot_path = q3 / f"snapshot_{version}.json"
snapshot_path.write_text(json.dumps(snapshot_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"version": version, "file_count": len(snapshot)}, ensure_ascii=False))
