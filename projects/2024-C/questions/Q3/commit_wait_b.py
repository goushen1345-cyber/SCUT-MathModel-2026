from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 32 and state["stage"] == "TRIAL" and state["active_question"] == "Q3"
assert any(a["id"] == "U018" and a["plan_version"] == "Q3-TRIAL-v1" for a in state["authorizations"])

state["revision"] = 33
state["stage"] = "WAIT_B"
state["execution_status"] = "WAITING"
state["pending_gate"] = {
    "id": "B",
    "plan_version": "Q3-B-v1",
    "scope": "Q3",
    "summary": "选择Q3初始主方案。AI建议保留B0（冻结Q2的M0-R1），以M0-CORR和M1-NET作深化对照；M2-RELROB因R1预算停止而证据不足。",
    "allowed_actions": "只读查看、解释和审查Q3-B-v1；等待用户明确选择或要求回A重设计划。不得深化、生成500样本留出、冻结Q3或进入论文阶段。",
    "budget": "本轮无运行预算；若选择B0进入深化方案设计，将另行提出C点预算。",
    "stop_condition": "收到用户对Q3-B-v1的明确模型选择后才进入深化方案设计；当前保持WAIT_B。",
}
state["q3_protocol"].update({
    "status": "WAITING_FOR_B_SELECTION",
    "experiments_run": 5,
    "trial_attempted_solves": 6,
    "trial_result": "Q3-B-v1",
    "recommended_initial_model": "B0",
    "comparison_models": ["M0-CORR", "M1-NET"],
    "m2_status": "INCONCLUSIVE_R1_BUDGET_STOP",
    "future_holdout_opened": False,
})
state["data_scope"]["modeling_authorized"] = "Q3 trial U018 completed at WAIT_B; no deepening or further solve authorized."
state["history"].append({
    "date": "2026-09-08", "from_stage": "TRIAL", "to_stage": "WAIT_B", "authorization_id": "U018",
    "reason": "完成Q3-TRIAL-v1关系生成、候选试跑和独立比较。四份有效方案面积相同且0硬约束违规；M2-R1在预算边界未完成。AI建议保留B0，停B等待人工选择。",
    "artifacts": [
        "questions/Q3/generate_scenarios.py", "questions/Q3/run_trials.py", "questions/Q3/refine_trials_gap.py", "questions/Q3/verify_trials.py",
        "questions/Q3/runs/scenarios/validation.json", "questions/Q3/runs/validation.json", "questions/Q3/runs/completion.json", "questions/Q3/runs/budget_stop.json",
        "questions/Q3/runs/primary_summary.csv", "questions/Q3/runs/pairwise_comparison.csv", "questions/Q3/runs/plan_similarity.csv",
        "questions/Q3/report.md", "questions/Q3/experiments.md", "paper_evidence/Q3.md", "state/decisions.md", "state/ai_usage_log.md"
    ],
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
