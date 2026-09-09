from pathlib import Path
import json

project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 20 and state["stage"] == "FROZEN"
assert state["questions"]["Q1"]["frozen_version"] == "Q1-D-v2-candidate"
quote = "“冻结 Q1-D-v2-candidate，并进入 Q2 候选准备，做到 A，不运行实验。”"
state["revision"] = 21
state["stage"] = "CANDIDATES"
state["execution_status"] = "ACTIVE"
state["active_question"] = "Q2"
state["pending_gate"] = None
state["questions"]["Q2"]["status"] = "ACTIVE"
state["authorizations"].append({
    "id": "U012", "from_stage": "FROZEN", "to_stage": "CANDIDATES", "scope": "Q2",
    "plan_version": "Q2-ENTRY-v1", "user_quote": quote,
    "message_ref": "当前任务用户最新明确冻结并进入Q2消息", "confirmed_by": "user", "recorded_date": "2026-09-07",
    "boundary": "进入Q2候选准备，形成候选与固定试跑计划并停A；不得运行实验、修改冻结数据或覆盖Q1冻结快照。"
})
state["history"].append({
    "date": "2026-09-07", "from_stage": "FROZEN", "to_stage": "CANDIDATES", "authorization_id": "U012",
    "reason": "用户在同一明确消息中授权进入Q2候选准备并停A。Q2与Q1无题面硬依赖，但复用已验证的农业约束和收益计算；本阶段不运行实验。",
    "artifacts": []
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
