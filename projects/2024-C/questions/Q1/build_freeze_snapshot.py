from pathlib import Path
import hashlib, json

project = Path(__file__).resolve().parents[2]
q = project / "questions/Q1"
version = "Q1-D-v2-candidate"
record_path = q / "freeze_record_Q1-D-v2-candidate.json"
record = {
    "version": version,
    "authorization": "U011",
    "status": "FROZEN_BY_USER",
    "data_version": "G1-v1-base",
    "final_s1": "boost_runs/BOOST-D0-S1/solution.csv",
    "final_s2": "deep_runs/M1R3-D0-S2/solution.csv",
    "output_s1": "outputs/Q1-DRAFT-v2/result1_1_Q1-DRAFT-v2.xlsx",
    "output_s2": "outputs/Q1-DRAFT-v1/result1_2_Q1-DRAFT-v1.xlsx",
    "limitations": [
        "Demand values are scenario assumptions rather than observed sales.",
        "Prices use interval midpoint candidates.",
        "S1 is a time-limited feasible solution and is not proven globally optimal.",
        "The aggregate bean-area rule does not prove within-plot spatial coverage.",
        "The final boost batch exceeded its 12-minute end-to-end budget by about 0.95 minute; solver scope was unchanged."
    ],
    "human_verification": "User authorized freezing the named version; item-by-item manual recalculation is not claimed."
}
record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

files = {}
for manifest_path in (q / "deep_runs/manifest.json", q / "boost_runs/manifest.json"):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        path = q / rel
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, (rel, expected, actual)
        files[f"questions/Q1/{rel}"] = actual

extra = [
    q / "freeze_record_Q1-D-v2-candidate.json",
    q / "report.md", q / "experiments.md",
    q / "protocols/demand_scenarios_v1.json", q / "protocols/deepen_v1.json", q / "protocols/s1_boost_v1.json",
    q / "run_trials.py", q / "repair_m1_warmstart.py", q / "run_deepen.py", q / "repair_pareto.py",
    q / "run_s1_boost.py", q / "verify_trials.py", q / "verify_deepen.py", q / "verify_workbooks.py",
    q / "verify_s1_boost.py", q / "verify_s1_workbook_v2.py",
    q / "runs/validation.json", q / "runs/comparison.csv",
    project / "paper_evidence/Q1.md"
]
for path in extra:
    files[path.relative_to(project).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

snapshot_path = q / "snapshot_Q1-D-v2-candidate.json"
snapshot_path.write_text(json.dumps({"version": version, "files": dict(sorted(files.items()))}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"version": version, "files": len(files), "snapshot": str(snapshot_path)}, ensure_ascii=False))
