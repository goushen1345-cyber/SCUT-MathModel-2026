from pathlib import Path
from datetime import datetime, timezone
import json

project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 35 and state["stage"] == "WAIT_C" and state["active_question"] == "Q3"
assert state["pending_gate"]["plan_version"] == "Q3-DEEPEN-v1"
assert state["q3_protocol"].get("future_holdout_opened") is False
quote = "批准 Q3-DEEPEN-v1：按 W1—W4 执行，预算25分钟，完成独立核验后停D；M2不重跑，不冻结Q3、不进入论文阶段。"
state["revision"] = 36
state["stage"] = "DEEPEN"
state["execution_status"] = "ACTIVE"
state["pending_gate"] = None
state["authorizations"].append({
    "id": "U020", "from_stage": "WAIT_C", "to_stage": "DEEPEN", "scope": "Q3",
    "plan_version": "Q3-DEEPEN-v1", "user_quote": quote,
    "message_ref": "当前任务用户对Q3 C点计划的明确批准消息", "confirmed_by": "user", "recorded_date": "2026-09-08",
    "boundary": "执行W1—W4，总墙钟25分钟；M2不重跑，完成独立核验后停D。不得冻结Q3或进入论文阶段。",
})
state["q3_protocol"].update({
    "status": "DEEPEN_ACTIVE", "deepen_authorization": "U020",
    "deepen_started_utc": datetime.now(timezone.utc).isoformat(), "future_holdout_opened": False,
})
state["history"].append({
    "date": "2026-09-08", "from_stage": "WAIT_C", "to_stage": "DEEPEN", "authorization_id": "U020",
    "reason": "用户明确批准Q3-DEEPEN-v1的W1—W4和25分钟预算；开始执行，独立核验后停D，M2不重跑。",
    "artifacts": [],
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
