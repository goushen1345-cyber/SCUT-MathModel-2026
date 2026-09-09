import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if state["revision"] != 36 or state["stage"] != "DEEPEN" or state["active_question"] != "Q3":
    raise SystemExit("Expected revision 36 at Q3 DEEPEN")

validation = json.loads((project / "questions/Q3/deep_runs/validation.json").read_text(encoding="utf-8"))
completion = json.loads((project / "questions/Q3/deep_runs/completion.json").read_text(encoding="utf-8"))
preselection = json.loads((project / "questions/Q3/deep_runs/preholdout_selection.json").read_text(encoding="utf-8"))
if not validation.get("passed"):
    raise SystemExit("Independent Q3 validation did not pass")
if validation.get("final_selection", {}).get("selected") != "B0":
    raise SystemExit("Independent final selection is not B0")
if preselection.get("challenger") is not None:
    raise SystemExit("Pre-holdout challenger was not locked as null")
if completion.get("m2_rerun") is not False:
    raise SystemExit("M2 rerun boundary was violated")

candidate = copy.deepcopy(state)
candidate["revision"] = 37
candidate["stage"] = "WAIT_D"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = {
    "id": "D",
    "plan_version": "Q3-D-v1-candidate",
    "scope": "Q3",
    "summary": "深化后继续选择B0。N10增益0.064%未达门槛；N30因邻域引用错误被排除；500底层留出只验证B0。等待决定冻结或另行设计补强。",
    "allowed_actions": "只读查看、解释和审查Q3-D-v1-candidate；等待用户明确冻结、继续深化或重选。不得自动修复或重跑N30、冻结Q3、改变留出协议或进入论文阶段。",
    "budget": "Q3-DEEPEN-v1从W1开始到最终独立核验约18.1分钟，未超过25分钟。若修复N30，必须另批新协议和独立新留出。",
    "stop_condition": "收到用户对Q3-D-v1-candidate的明确D点决定前停止研究。",
}
candidate["q3_protocol"].update({
    "status": "WAITING_FOR_D_DECISION",
    "deepen_result": "Q3-D-v1-candidate",
    "selected_candidate": "B0",
    "future_holdout_opened": True,
    "future_holdout_count": 500,
    "future_holdout_seed": 20250308,
    "holdout_world_evaluations": 1500,
    "deepen_completed_solves": 3,
    "valid_deepen_solves": 2,
    "excluded_deepen_run": "N30",
    "excluded_deepen_reason": "wrong Hamming reference to N10; 40 changes from B0 exceeded limit 30",
    "deepen_wall_minutes": 18.1,
    "independent_validation": "PASSED",
})
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "DEEPEN",
    "to_stage": "WAIT_D",
    "authorization_id": "U020",
    "reason": "完成Q3-DEEPEN-v1并通过独立核验。N10增益0.064%未达门槛；N30因错误邻域引用被排除且留出开放后未补跑。500底层留出只验证B0；最终形成Q3-D-v1-candidate并保留B0，约18.1分钟内停D。",
    "artifacts": [
        "questions/Q3/model_core_deepen.py",
        "questions/Q3/scenario_core_deepen.py",
        "questions/Q3/run_deepen.py",
        "questions/Q3/verify_deepen.py",
        "questions/Q3/protocols/deepen_v1.json",
        "questions/Q3/deep_runs/completion.json",
        "questions/Q3/deep_runs/validation.json",
        "questions/Q3/deep_runs/preholdout_selection.json",
        "questions/Q3/deep_runs/mechanism_by_crop_year.csv",
        "questions/Q3/deep_runs/sensitivity_summary.csv",
        "questions/Q3/deep_runs/holdout_summary.csv",
        "questions/Q3/report.md",
        "questions/Q3/experiments.md",
        "paper_evidence/Q3.md",
        "state/decisions.md",
        "state/ai_usage_log.md"
    ]
})
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
