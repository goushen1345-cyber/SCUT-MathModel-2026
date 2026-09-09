from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[2]
Q = Path(__file__).resolve().parent
VERSION = "Q2-D-v1-candidate"

record = {
    "version": VERSION,
    "authorization": "U016",
    "status": "FROZEN_BY_USER",
    "data_version": "G1-v1-base",
    "q1_reference": "Q1-D-v2-candidate",
    "selected_plan": "runs/M0-R1/solution.csv",
    "validated_plan_copy": "deep_runs/M0-DEEP-v1/solution.csv",
    "output": "outputs/Q2-DRAFT-v1/result2_Q2-DRAFT-v1.xlsx",
    "limitations": [
        "D05 normal sales are a production-based proxy, not observed sales.",
        "S2 half-price excess sales are the main interpretation; S1 can change model ranking.",
        "Scenario probabilities and independence structure are modeling assumptions, not estimates.",
        "The selected M0-R1 is a time-limited feasible solution, not proven globally optimal.",
        "The aggregate bean-area rule is accepted for this version; the strict whole-plot diagnostic has 23 violating land-window pairs.",
    ],
    "human_verification": "User authorized freezing the named version; item-by-item manual recalculation is not claimed.",
}
record_path = Q / f"freeze_record_{VERSION}.json"
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

files = []
for path in Q.rglob("*"):
    if not path.is_file():
        continue
    rel_q = path.relative_to(Q)
    if rel_q.parts[0] in (".artifact-q2", "__pycache__"):
        continue
    if path.name.startswith("commit_") or path.name in {"build_freeze_snapshot.py", "inspect_result2.py"}:
        continue
    if path.name.startswith("snapshot_Q2-"):
        continue
    files.append(path)
files.append(ROOT / "paper_evidence/Q2.md")

snapshot = {}
for path in sorted(set(files)):
    rel = path.relative_to(ROOT).as_posix()
    snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()

doc = {"version": VERSION, "files": snapshot, "file_count": len(snapshot)}
snapshot_path = Q / f"snapshot_{VERSION}.json"
snapshot_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"version": VERSION, "files": len(snapshot)}, ensure_ascii=False))
