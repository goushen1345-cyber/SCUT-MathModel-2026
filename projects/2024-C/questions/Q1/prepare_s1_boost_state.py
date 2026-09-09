from pathlib import Path
import json

project = Path(__file__).resolve().parents[2]
state_path = project / "state" / "state.json"
candidate_path = project / "state" / "proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["revision"] == 17 and state["stage"] == "WAIT_C"
assert state["pending_gate"]["plan_version"] == "Q1-S1-BOOST-v1"

state["revision"] = 18
state["stage"] = "DEEPEN"
state["execution_status"] = "ACTIVE"
state["pending_gate"] = None
state["questions"]["Q1"]["status"] = "ACTIVE"
state["authorizations"].append({
    "id": "U010",
    "from_stage": "WAIT_C",
    "to_stage": "DEEPEN",
    "scope": "Q1",
    "plan_version": "Q1-S1-BOOST-v1",
    "user_quote": "批准 Q1-S1-BOOST-v1：只补强 D0/S1 和 D10/S1，总预算12分钟，完成独立核验后停D；D05/S1和全部S2保持不变，不冻结Q1、不进入Q2。",
    "message_ref": "当前任务用户最新明确批准消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-07",
    "boundary": "只执行D0/S1与D10/S1的三阶段补强及独立核验，总墙钟12分钟；D05/S1与全部S2保持不变；停D，不冻结Q1、不进入Q2。",
})
state["history"].append({
    "date": "2026-09-07",
    "from_stage": "WAIT_C",
    "to_stage": "DEEPEN",
    "authorization_id": "U010",
    "reason": "收到Q1-S1-BOOST-v1明确批准，开始仅针对D0/S1和D10/S1的跨情形热启动补强；锁定D05/S1与全部S2。",
    "artifacts": [],
})
candidate_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
