import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state" / "state.json"
candidate_path = project / "state" / "proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))

if state["revision"] != 25 or state["stage"] != "DEEPEN_PLAN":
    raise SystemExit("Expected Q2 revision 25 at DEEPEN_PLAN")
if state["q2_protocol"].get("future_holdout_opened") is not False:
    raise SystemExit("Reserved holdout must remain unopened during design")

candidate = copy.deepcopy(state)
candidate["revision"] = 26
candidate["stage"] = "WAIT_C"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = {
    "id": "C",
    "plan_version": "Q2-DEEPEN-v1",
    "scope": "Q2",
    "summary": "执行M0三阶段补强、一次性500留出比较、概率与销售口径敏感性、独立核验和Q2项目草稿；完成后停D。",
    "allowed_actions": "只读查看、解释和审查Q2-DEEPEN-v1；等待用户明确批准。不得运行求解、生成或查看500留出情形、创建result2草稿、冻结Q2或进入Q3。",
    "budget": "建议总墙钟25分钟：W1 8分钟、W2 7分钟、W3 4分钟、W4 6分钟。",
    "stop_condition": "只有收到用户对Q2-DEEPEN-v1范围和25分钟预算的明确批准后才执行；执行完成并独立核验后停D。",
}
candidate["q2_protocol"].update(
    {
        "status": "WAITING_FOR_C_APPROVAL",
        "deepen_plan": "Q2-DEEPEN-v1",
        "future_holdout_opened": False,
    }
)
candidate["history"].append(
    {
        "date": "2026-09-07",
        "from_stage": "DEEPEN_PLAN",
        "to_stage": "WAIT_C",
        "authorization_id": "U014",
        "reason": "完成Q2-DEEPEN-v1设计：围绕已选M0预注册补强、一次性留出验证、假设敏感性、独立核验与草稿导出；未运行实验、未生成留出情形或工作簿，停C。",
        "artifacts": [
            "questions/Q2/protocols/deepen_v1.json",
            "questions/Q2/report.md",
            "questions/Q2/experiments.md",
            "paper_evidence/Q2.md",
            "state/decisions.md",
            "state/ai_usage_log.md",
        ],
    }
)

candidate_path.write_text(
    json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
