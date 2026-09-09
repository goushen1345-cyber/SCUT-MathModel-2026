from pathlib import Path
import json

project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 21 and state["stage"] == "CANDIDATES" and state["active_question"] == "Q2"
assert state["questions"]["Q1"]["frozen_version"] == "Q1-D-v2-candidate"
state["revision"] = 22
state["stage"] = "WAIT_A"
state["execution_status"] = "WAITING"
state["pending_gate"] = {
    "id": "A",
    "plan_version": "Q2-TRIAL-v1",
    "scope": "Q2",
    "summary": "决定是否按Q2-UNCERTAINTY-v1试跑B0、M0、M1、M2、M3，并接受D05主基准、S2主销售规则及低中高三点概率作为明确建模假设。",
    "allowed_actions": "只读查看、解释和审查Q2-A-v1与Q2-TRIAL-v1；等待用户明确批准或修改。不得生成随机情形、运行模型、创建result2.xlsx、冻结Q2或进入Q3。",
    "budget": "拟议总墙钟55分钟：情形生成与检查5分钟，候选求解40分钟，独立比较与报告10分钟。",
    "stop_condition": "收到用户对Q2-TRIAL-v1及三个工作口径的明确批准后才运行；完成后停B。"
}
state["q1_protocol"]["status"] = "FROZEN"
state["q1_protocol"]["deepen_result"] = "Q1-D-v2-candidate"
state["q1_protocol"]["s1_boost_result"] = "Q1-D-v2-candidate"
state["q2_protocol"] = {
    "version": "Q2-A-v1", "uncertainty": "Q2-UNCERTAINTY-v1", "trial_plan": "Q2-TRIAL-v1",
    "data_version": "G1-v1-base", "q1_reference": "Q1-D-v2-candidate",
    "status": "WAITING_FOR_A_APPROVAL", "experiments_run": 0
}
state["data_scope"]["modeling_authorized"] = "Q2 candidate preparation under U012; completed at WAIT_A. No Q2 experiment authorized."
state["history"].append({
    "date": "2026-09-07", "from_stage": "CANDIDATES", "to_stage": "WAIT_A", "authorization_id": "U012",
    "reason": "完成Q2-A-v1候选准备和Q2-TRIAL-v1固定试跑计划。比较B0/M0/M1/M2/M3，明确销量基准、销售规则、概率分布、训练/比较隔离、预算与停止条件；未运行实验或生成result2.xlsx。",
    "artifacts": ["questions/Q2/report.md", "questions/Q2/experiments.md", "questions/Q2/protocols/uncertainty_v1.json", "questions/Q2/protocols/trial_v1.json", "paper_evidence/Q2.md", "state/decisions.md", "state/ai_usage_log.md"]
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
