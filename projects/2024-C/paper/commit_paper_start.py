import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[1]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
if state["revision"] != 40 or state["stage"] != "WAIT_P":
    raise SystemExit("Expected revision 40 at WAIT_P")
if state["pending_gate"].get("plan_version") != "PAPER-PLAN-v1":
    raise SystemExit("Unexpected P-point plan")

candidate = copy.deepcopy(state)
candidate["revision"] = 41
candidate["stage"] = "PAPER"
candidate["execution_status"] = "ACTIVE"
candidate["pending_gate"] = None
candidate["authorizations"].append({
    "id": "U023",
    "from_stage": "WAIT_P",
    "to_stage": "PAPER",
    "scope": "PAPER",
    "plan_version": "PAPER-PLAN-v1",
    "user_quote": "批准 PAPER-PLAN-v1：按建议故事线和八部分结构写全文，制作计划中的图表，基于冻结证据复核三本结果表，不补实验、不修改冻结结论；完成DOCX、PDF和独立核验后停FINAL。",
    "message_ref": "当前任务用户对P点论文方案的明确批准消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "按八部分结构写全文并制作计划图表，复核三本结果表，生成DOCX/PDF并独立核验后停FINAL；不得补实验、修改冻结结论或对外提交。",
})
candidate["paper_protocol"].update({
    "status": "PAPER_ACTIVE",
    "paper_authorization": "U023",
    "full_draft_authorized": True,
    "new_experiments_authorized": False,
    "external_submission_authorized": False,
})
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "WAIT_P",
    "to_stage": "PAPER",
    "authorization_id": "U023",
    "reason": "用户批准PAPER-PLAN-v1，开始基于冻结证据写八部分全文、制作计划图表、复核三本结果表并生成DOCX/PDF；完成独立核验后停FINAL，不补实验或修改冻结结论。",
    "artifacts": [],
})
(project / "state/proposed.json").write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
