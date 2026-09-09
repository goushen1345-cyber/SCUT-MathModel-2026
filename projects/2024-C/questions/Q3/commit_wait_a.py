from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["revision"] == 30 and state["stage"] == "CANDIDATES" and state["active_question"] == "Q3"
assert state["questions"]["Q2"]["frozen_version"] == "Q2-D-v1-candidate"

state["revision"] = 31
state["stage"] = "WAIT_A"
state["execution_status"] = "WAITING"
state["pending_gate"] = {
    "id": "A",
    "plan_version": "Q3-TRIAL-v1",
    "scope": "Q3",
    "summary": "决定是否接受Q3-RELATION-v1的合成相关性与R0/RS/RSC关系世界，并试跑B0、M0-CORR、M1-NET、M2-RELROB。",
    "allowed_actions": "只读查看、解释和审查Q3-A-v1；等待用户明确批准或修改。不得生成Q3随机情形或关系图、运行求解/评价、打开500样本留出集、冻结Q3或进入论文阶段。",
    "budget": "拟议总墙钟50分钟：关系图和情形生成/核验7分钟，M0-CORR 8分钟，M1-NET 12分钟，M2-RELROB 15分钟，统一比较与独立复算8分钟。",
    "stop_condition": "收到用户对Q3-TRIAL-v1及Q3-RELATION-v1模拟口径的明确批准后才运行；完成后停B。",
}
state["q3_protocol"]["status"] = "WAITING_FOR_A_APPROVAL"
state["history"].append({
    "date": "2026-09-08",
    "from_stage": "CANDIDATES",
    "to_stage": "WAIT_A",
    "authorization_id": "U017",
    "reason": "完成Q3-A-v1候选准备：将不可识别的相关性、替代和互补关系写成透明模拟协议，设计四候选、统一比较、反证、门槛、预算与停止条件；实验计数0。",
    "artifacts": [
        "questions/Q3/report.md",
        "questions/Q3/experiments.md",
        "questions/Q3/protocols/relationship_v1.json",
        "questions/Q3/protocols/trial_v1.json",
        "paper_evidence/Q3.md",
        "state/decisions.md",
        "state/ai_usage_log.md",
    ],
})
candidate_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
