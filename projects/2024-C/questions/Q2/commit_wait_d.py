import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if state["revision"] != 27 or state["stage"] != "DEEPEN":
    raise SystemExit("Expected revision 27 at DEEPEN")
validation = json.loads((project / "questions/Q2/deep_runs/validation.json").read_text(encoding="utf-8"))
workbook = json.loads((project / "questions/Q2/outputs/Q2-DRAFT-v1/workbook_validation.json").read_text(encoding="utf-8"))
completion = json.loads((project / "questions/Q2/deep_runs/completion.json").read_text(encoding="utf-8"))
if not (validation["passed"] and workbook["passed"] and completion["within_budget"]):
    raise SystemExit("Q2 deep acceptance failed")

candidate = copy.deepcopy(state)
candidate["revision"] = 28
candidate["stage"] = "WAIT_D"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = {
    "id": "D",
    "plan_version": "Q2-D-v1-candidate",
    "scope": "Q2",
    "summary": "M0-R1保留为Q2候选；500留出验证和项目草稿核验通过。严格整块豆类诊断仍有23个违规窗口，等待决定冻结或继续补强。",
    "allowed_actions": "只读查看、解释和审查Q2-D-v1-candidate；等待用户明确冻结、继续深化或重选。不得自动冻结Q2、修改留出协议或进入Q3。",
    "budget": "Q2-DEEPEN-v1实际23.40分钟，未超过25分钟。严格整块豆类补强若选择，建议另批12—18分钟。",
    "stop_condition": "收到用户对Q2-D-v1-candidate的明确D点决定前停止研究。",
}
candidate["q2_protocol"].update({
    "status": "WAITING_FOR_D_DECISION",
    "deepen_result": "Q2-D-v1-candidate",
    "selected_candidate": "M0-R1",
    "future_holdout_opened": True,
    "future_holdout_count": 500,
    "future_holdout_seed": 20241107,
    "draft_workbook": "questions/Q2/outputs/Q2-DRAFT-v1/result2_Q2-DRAFT-v1.xlsx",
    "strict_bean_diagnostic_violations": 23,
    "deepen_wall_minutes": completion["wall_minutes"],
})
candidate["history"].append({
    "date": "2026-09-07",
    "from_stage": "DEEPEN",
    "to_stage": "WAIT_D",
    "authorization_id": "U015",
    "reason": "完成Q2-DEEPEN-v1，23.40分钟内通过独立数值与工作簿核验；保留M0-R1为Q2-D-v1-candidate。严格整块豆类诊断有23个违规窗口，作为限制停D；未冻结Q2或进入Q3。",
    "artifacts": [
        "questions/Q2/run_deepen.py",
        "questions/Q2/verify_deepen.py",
        "questions/Q2/verify_workbook_q2.py",
        "questions/Q2/deep_runs/validation.json",
        "questions/Q2/deep_runs/holdout_summary.csv",
        "questions/Q2/deep_runs/holdout_pairwise.csv",
        "questions/Q2/deep_runs/sensitivity_summary.csv",
        "questions/Q2/deep_runs/contribution_difference.csv",
        "questions/Q2/deep_runs/completion.json",
        "questions/Q2/deep_runs/manifest.json",
        "questions/Q2/outputs/Q2-DRAFT-v1/result2_Q2-DRAFT-v1.xlsx",
        "questions/Q2/outputs/Q2-DRAFT-v1/workbook_validation.json",
        "questions/Q2/report.md",
        "questions/Q2/experiments.md",
        "paper_evidence/Q2.md",
        "state/decisions.md",
        "state/ai_usage_log.md"
    ]
})
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
