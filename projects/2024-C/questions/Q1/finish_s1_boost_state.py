from pathlib import Path
import json

project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
assert state["revision"] == 18 and state["stage"] == "DEEPEN"
assert any(a["id"] == "U010" for a in state["authorizations"])

state["revision"] = 19
state["stage"] = "WAIT_D"
state["execution_status"] = "WAITING"
state["pending_gate"] = {
    "id": "D",
    "plan_version": "Q1-D-v2-candidate",
    "scope": "Q1",
    "summary": "决定是否冻结Q1-D-v2-candidate，或提出下一轮明确深化/重选方案；当前候选包含补强后的S1、保持不变的S2及S1草稿v2。",
    "allowed_actions": "只读查看、解释和审查Q1-D-v2-candidate；等待用户明确冻结、继续深化或重选。不得自行冻结Q1或进入Q2。",
    "budget": "本轮Q1-S1-BOOST-v1已结束；不再运行实验。",
    "stop_condition": "收到用户对Q1-D-v2-candidate的明确决定前保持WAIT_D。冻结Q1与进入Q2分别需要明确授权。"
}
state["history"].append({
    "date": "2026-09-07",
    "from_stage": "DEEPEN",
    "to_stage": "WAIT_D",
    "authorization_id": "U010",
    "reason": "完成Q1-S1-BOOST-v1：两个目标三阶段求解和独立核验通过，0硬约束违规；40个锁定文件不变；生成并逐格核验S1草稿v2。求解9.54分钟，端到端12.95分钟，记录超预算0.95分钟偏差。形成Q1-D-v2-candidate，未冻结、未进入Q2。",
    "artifacts": [
        "questions/Q1/run_s1_boost.py",
        "questions/Q1/verify_s1_boost.py",
        "questions/Q1/verify_s1_workbook_v2.py",
        "questions/Q1/boost_runs/validation.json",
        "questions/Q1/boost_runs/comparison.csv",
        "questions/Q1/boost_runs/cross_evaluation.csv",
        "questions/Q1/boost_runs/scenario_similarity.csv",
        "questions/Q1/boost_runs/completion.json",
        "questions/Q1/boost_runs/manifest.json",
        "questions/Q1/outputs/Q1-DRAFT-v2/result1_1_Q1-DRAFT-v2.xlsx",
        "questions/Q1/outputs/Q1-DRAFT-v2/workbook_validation.json",
        "questions/Q1/report.md",
        "questions/Q1/experiments.md",
        "paper_evidence/Q1.md",
        "state/decisions.md",
        "state/ai_usage_log.md"
    ]
})
candidate_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
