from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 31 and state["stage"] == "WAIT_A" and state["active_question"] == "Q3"
assert state["pending_gate"]["plan_version"] == "Q3-TRIAL-v1"
quote = "批准 Q3-TRIAL-v1：按 Q3-RELATION-v1 试跑 B0、M0-CORR、M1-NET、M2-RELROB，预算50分钟，完成独立比较后停B。"
state["revision"] = 32
state["stage"] = "TRIAL"
state["execution_status"] = "ACTIVE"
state["pending_gate"] = None
state["authorizations"].append({
    "id": "U018",
    "from_stage": "WAIT_A",
    "to_stage": "TRIAL",
    "scope": "Q3",
    "plan_version": "Q3-TRIAL-v1",
    "user_quote": quote,
    "message_ref": "当前任务用户最新明确A点批准消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "按Q3-RELATION-v1试跑B0、M0-CORR、M1-NET、M2-RELROB，总墙钟50分钟并独立比较后停B；不得打开预留500样本、深化、冻结Q3或进入论文阶段。",
})
state["q3_protocol"]["status"] = "TRIAL_ACTIVE"
state["q3_protocol"]["trial_authorization"] = "U018"
state["history"].append({
    "date": "2026-09-08",
    "from_stage": "WAIT_A",
    "to_stage": "TRIAL",
    "authorization_id": "U018",
    "reason": "收到Q3-TRIAL-v1明确批准，开始固定关系协议下的四候选试跑；总墙钟50分钟，完成独立比较后停B。",
    "artifacts": [],
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
