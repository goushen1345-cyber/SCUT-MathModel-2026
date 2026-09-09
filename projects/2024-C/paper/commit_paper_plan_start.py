import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[1]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if state["revision"] != 38 or state["stage"] != "FROZEN":
    raise SystemExit("Expected revision 38 at FROZEN")
if not all(q["status"] == "FROZEN" and q["validity"] == "VALID" for q in state["questions"].values()):
    raise SystemExit("All questions must be valid and frozen")

candidate = copy.deepcopy(state)
candidate["revision"] = 39
candidate["stage"] = "PAPER_PLAN"
candidate["execution_status"] = "ACTIVE"
candidate["pending_gate"] = None
candidate["authorizations"].append({
    "id": "U022",
    "from_stage": "FROZEN",
    "to_stage": "PAPER_PLAN",
    "scope": "Q3",
    "plan_version": "PAPER-PLAN-v1",
    "user_quote": "进入论文方案准备：基于Q1、Q2、Q3冻结证据设计故事线、章节、图表和验证清单，做到P，不写全文、不补实验。",
    "message_ref": "当前任务用户对冻结三问进入论文方案阶段的明确消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "只基于冻结证据设计故事线、章节、图表和验证清单，完成后停P；不得写全文、补实验或修改冻结成果。",
})
candidate["paper_protocol"] = {
    "version": "PAPER-PLAN-v1",
    "status": "PLANNING_ACTIVE",
    "authorization": "U022",
    "frozen_inputs": {
        "data": "G1-v1-base",
        "Q1": "Q1-D-v2-candidate",
        "Q2": "Q2-D-v1-candidate",
        "Q3": "Q3-D-v1-candidate",
    },
    "full_draft_authorized": False,
    "new_experiments_authorized": False,
}
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "FROZEN",
    "to_stage": "PAPER_PLAN",
    "authorization_id": "U022",
    "reason": "三问均有效冻结后，用户明确授权基于冻结证据设计论文故事线、章节、图表和验证清单，完成停P；不写全文、不补实验。",
    "artifacts": [],
})
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
