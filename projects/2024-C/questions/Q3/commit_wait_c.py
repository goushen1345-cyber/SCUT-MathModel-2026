from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 34 and state["stage"] == "DEEPEN_PLAN"
assert state["active_question"] == "Q3"
assert state["q3_protocol"].get("future_holdout_opened") is False

state["revision"] = 35
state["stage"] = "WAIT_C"
state["execution_status"] = "WAITING"
state["pending_gate"] = {
    "id": "C",
    "plan_version": "Q3-DEEPEN-v1",
    "scope": "Q3",
    "summary": "执行关系贡献分解、B0附近N0/N10/N30挑战、关系强度与销量口径敏感性，并在候选预选后一次性打开500底层留出；独立核验后停D。",
    "allowed_actions": "只读查看、解释和审查Q3-DEEPEN-v1；等待用户明确批准。不得运行局部求解、生成或查看500留出、改变关系参数、重跑M2、冻结Q3或进入论文阶段。",
    "budget": "建议总墙钟25分钟：W1 3分钟、W2 12分钟、W3 4分钟、W4 6分钟。",
    "stop_condition": "只有收到用户对Q3-DEEPEN-v1范围、留出访问和25分钟预算的明确批准后才执行；到25分钟立即停止未完成项，完成独立核验后停D。",
}
state["q3_protocol"].update({
    "status": "WAITING_FOR_C_APPROVAL",
    "deepen_plan": "Q3-DEEPEN-v1",
    "future_holdout_opened": False,
})
state["history"].append({
    "date": "2026-09-08",
    "from_stage": "DEEPEN_PLAN",
    "to_stage": "WAIT_C",
    "authorization_id": "U019",
    "reason": "完成Q3-DEEPEN-v1设计：用关系贡献分解、局部邻域、强度敏感性和一次性留出检验已选B0；固定门槛、25分钟预算和停止条件。未运行实验或生成留出，停C。",
    "artifacts": [
        "questions/Q3/protocols/deepen_v1.json",
        "questions/Q3/report.md",
        "questions/Q3/experiments.md",
        "paper_evidence/Q3.md",
        "state/decisions.md",
        "state/ai_usage_log.md",
    ],
})
(project / "state/proposed.json").write_text(
    json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
