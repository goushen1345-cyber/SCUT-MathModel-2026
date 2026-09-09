import copy
import json
from pathlib import Path


project = Path(__file__).resolve().parents[1]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
if state["revision"] != 39 or state["stage"] != "PAPER_PLAN":
    raise SystemExit("Expected revision 39 at PAPER_PLAN")
validation = json.loads((project / "paper/plan_validation_v1.json").read_text(encoding="utf-8"))
if not validation.get("passed") or validation.get("new_experiments_run") is not False:
    raise SystemExit("Paper plan validation failed or experiment boundary was violated")

candidate = copy.deepcopy(state)
candidate["revision"] = 40
candidate["stage"] = "WAIT_P"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = {
    "id": "P",
    "plan_version": "PAPER-PLAN-v1",
    "scope": "PAPER",
    "summary": "已基于三个有效冻结版本形成论文故事线、八部分章节、9图8表、20条证据矩阵和全文验证清单，等待确认后再写全文。",
    "allowed_actions": "只读查看、解释和审查PAPER-PLAN-v1；可按用户意见修改为新方案版本。未经明确批准不得写全文、生成正式图表或文档、修改冻结成果、补实验或对外提交。",
    "budget": "本阶段无实验预算。后续全文工作量和停止条件将在P点批准范围内执行。",
    "stop_condition": "收到用户对PAPER-PLAN-v1的明确批准或修改意见前停止论文制作。",
}
candidate["paper_protocol"].update({
    "status": "WAITING_FOR_P_APPROVAL",
    "plan_result": "PAPER-PLAN-v1",
    "recommended_title": "基于混合整数规划、情景模拟与关系敏感性分析的农作物种植策略",
    "recommended_storyline": "统一农业排程，逐层加入滞销规则、参数波动和市场关系，并以预注册门槛决定是否改变方案",
    "planned_sections": 8,
    "planned_figures": 9,
    "planned_tables": 8,
    "evidence_claims": 20,
    "plan_validation": "PASSED",
    "full_draft_authorized": False,
    "new_experiments_authorized": False,
})
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "PAPER_PLAN",
    "to_stage": "WAIT_P",
    "authorization_id": "U022",
    "reason": "完成PAPER-PLAN-v1：基于三问冻结证据形成统一故事线、八部分章节、9图8表、20条证据矩阵和验证清单；9类计划核验通过，未写全文或补实验，停P等待人工确认。",
    "artifacts": [
        "paper/plan_v1.md",
        "paper/evidence_matrix_v1.csv",
        "paper/validation_checklist_v1.md",
        "paper/verify_plan_v1.py",
        "paper/plan_validation_v1.json",
        "state/decisions.md",
        "state/ai_usage_log.md"
    ],
})
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
