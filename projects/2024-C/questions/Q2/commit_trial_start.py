from pathlib import Path
import json

project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 22 and state["stage"] == "WAIT_A" and state["active_question"] == "Q2"
assert state["pending_gate"]["plan_version"] == "Q2-TRIAL-v1"
quote = "批准 Q2-TRIAL-v1，按 Q2-UNCERTAINTY-v1 试跑 B0、M0、M1、M2、M3，预算55分钟，完成独立比较后停B。"
state["revision"] = 23
state["stage"] = "TRIAL"
state["execution_status"] = "ACTIVE"
state["pending_gate"] = None
state["authorizations"].append({
    "id": "U013", "from_stage": "WAIT_A", "to_stage": "TRIAL", "scope": "Q2",
    "plan_version": "Q2-TRIAL-v1", "user_quote": quote,
    "message_ref": "当前任务用户最新明确A点批准消息", "confirmed_by": "user", "recorded_date": "2026-09-07",
    "boundary": "按Q2-UNCERTAINTY-v1试跑B0/M0/M1/M2/M3，总墙钟55分钟并独立比较后停B；不深化、不生成result2.xlsx、不冻结Q2、不进入Q3。"
})
state["q2_protocol"]["status"] = "TRIAL_ACTIVE"
state["history"].append({
    "date": "2026-09-07", "from_stage": "WAIT_A", "to_stage": "TRIAL", "authorization_id": "U013",
    "reason": "收到Q2-TRIAL-v1明确批准，开始固定情形协议下的B0/M0/M1/M2/M3试跑；预算55分钟，完成停B。",
    "artifacts": []
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
