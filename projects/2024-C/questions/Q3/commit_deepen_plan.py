from pathlib import Path
import json


project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 33 and state["stage"] == "WAIT_B" and state["active_question"] == "Q3"
assert state["pending_gate"]["plan_version"] == "Q3-B-v1"
quote = "批准 Q3-B-v1，选择 B0 作为初始主方案，保留 M0-CORR 和 M1-NET 作为深化对照，M2-RELROB 暂列证据不足；进入深化方案设计，完成后停C。"

state["revision"] = 34
state["stage"] = "DEEPEN_PLAN"
state["execution_status"] = "ACTIVE"
state["pending_gate"] = None
state["authorizations"].append({
    "id": "U019", "from_stage": "WAIT_B", "to_stage": "DEEPEN_PLAN", "scope": "Q3",
    "plan_version": "Q3-B-v1", "user_quote": quote,
    "message_ref": "当前任务用户对Q3-B-v1的明确选择消息", "confirmed_by": "user", "recorded_date": "2026-09-08",
    "boundary": "记录B0为Q3初始主方案，M0-CORR/M1-NET为深化对照，M2-RELROB暂列证据不足；只设计深化方案并停C，不运行模型、生成500留出或冻结Q3。",
})
state["q3_protocol"].update({
    "status": "DEEPEN_PLAN_DESIGN", "selected_initial_model": "B0",
    "selection_authorization": "U019", "comparison_models": ["M0-CORR", "M1-NET"],
    "m2_status": "INCONCLUSIVE_NOT_SELECTED_FOR_DEEPEN_SOLVE",
})
state["history"].append({
    "date": "2026-09-08", "from_stage": "WAIT_B", "to_stage": "DEEPEN_PLAN", "authorization_id": "U019",
    "reason": "用户选择B0为Q3初始主方案，保留M0-CORR/M1-NET作对照并暂置M2；开始深化方案设计，不运行实验。",
    "artifacts": [],
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
