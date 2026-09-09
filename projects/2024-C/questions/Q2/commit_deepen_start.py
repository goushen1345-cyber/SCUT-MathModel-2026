import copy
import json
from datetime import datetime, timezone
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state" / "state.json"
candidate_path = project / "state" / "proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))

if state["revision"] != 26 or state["stage"] != "WAIT_C":
    raise SystemExit("Expected revision 26 at WAIT_C")
if state["pending_gate"]["plan_version"] != "Q2-DEEPEN-v1":
    raise SystemExit("Q2-DEEPEN-v1 is not the pending C plan")
if state["q2_protocol"].get("future_holdout_opened") is not False:
    raise SystemExit("Reserved holdout was opened before authorization")

candidate = copy.deepcopy(state)
candidate["revision"] = 27
candidate["stage"] = "DEEPEN"
candidate["execution_status"] = "ACTIVE"
candidate["pending_gate"] = None
candidate["authorizations"].append(
    {
        "id": "U015",
        "from_stage": "WAIT_C",
        "to_stage": "DEEPEN",
        "scope": "Q2",
        "plan_version": "Q2-DEEPEN-v1",
        "user_quote": "批准 Q2-DEEPEN-v1，按 W1—W4 执行，预算25分钟，完成独立核验后停D；不冻结Q2、不进入Q3。",
        "message_ref": "当前任务用户对Q2 C点计划的明确批准消息",
        "confirmed_by": "user",
        "recorded_date": "2026-09-07",
        "boundary": "按W1—W4执行，总墙钟25分钟；完成独立核验后停D。不得冻结Q2或进入Q3。",
    }
)
started = datetime.now(timezone.utc).isoformat()
candidate["q2_protocol"].update(
    {
        "status": "DEEPEN_ACTIVE",
        "deepen_authorization": "U015",
        "deepen_started_utc": started,
        "future_holdout_opened": False,
    }
)
candidate["history"].append(
    {
        "date": "2026-09-07",
        "from_stage": "WAIT_C",
        "to_stage": "DEEPEN",
        "authorization_id": "U015",
        "reason": "用户明确批准Q2-DEEPEN-v1的W1—W4和25分钟预算；开始执行，完成独立核验后停D，不冻结Q2、不进入Q3。",
        "artifacts": [],
    }
)
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(started)
