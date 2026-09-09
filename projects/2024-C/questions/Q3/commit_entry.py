from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["revision"] == 29 and state["stage"] == "FROZEN"
assert state["questions"]["Q2"]["frozen_version"] == "Q2-D-v1-candidate"

state["revision"] = 30
state["stage"] = "CANDIDATES"
state["execution_status"] = "ACTIVE"
state["active_question"] = "Q3"
state["pending_gate"] = None
state["authorizations"].append({
    "id": "U017",
    "from_stage": "FROZEN",
    "to_stage": "CANDIDATES",
    "scope": "Q3",
    "plan_version": "Q3-ENTRY-v1",
    "user_quote": "冻结 Q2-D-v1-candidate，并进入 Q3 候选准备，做到 A，不运行实验。",
    "message_ref": "当前任务用户明确冻结Q2并进入Q3的消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "进入Q3并完成候选、模拟关系协议、公平比较和预算设计，到A停止；不生成Q3随机情形，不运行求解或评估，不冻结Q3。",
})
state["questions"]["Q3"].update({"status": "ACTIVE", "validity": "VALID"})
state["questions"]["Q3"]["depends_on"] = [{"question": "Q2", "version": "Q2-D-v1-candidate"}]
state["q3_protocol"] = {
    "version": "Q3-A-v1",
    "relationship_protocol": "Q3-RELATION-v1",
    "trial_plan": "Q3-TRIAL-v1",
    "data_version": "G1-v1-base",
    "q2_reference": "Q2-D-v1-candidate",
    "q2_plan": "M0-R1",
    "status": "CANDIDATE_PREPARATION",
    "experiments_run": 0,
}
state["data_scope"]["modeling_authorized"] = "Q3 candidate preparation under U017; no Q3 experiment authorized."
state["history"].append({
    "date": "2026-09-08",
    "from_stage": "FROZEN",
    "to_stage": "CANDIDATES",
    "authorization_id": "U017",
    "reason": "用户明确进入Q3候选准备到A，不运行实验；将Q3依赖绑定冻结Q2-D-v1-candidate。",
    "artifacts": [],
})
candidate_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
