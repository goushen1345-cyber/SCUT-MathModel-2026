from pathlib import Path
import hashlib, json

project = Path(__file__).resolve().parents[2]
state = json.loads((project / "state/state.json").read_text(encoding="utf-8"))
assert state["revision"] == 19 and state["stage"] == "WAIT_D" and state["active_question"] == "Q1"
snapshot_doc = json.loads((project / "questions/Q1/snapshot_Q1-D-v2-candidate.json").read_text(encoding="utf-8"))
snapshot = snapshot_doc["files"]
snapshot["questions/Q1/snapshot_Q1-D-v2-candidate.json"] = hashlib.sha256((project / "questions/Q1/snapshot_Q1-D-v2-candidate.json").read_bytes()).hexdigest()
assert all(hashlib.sha256((project / p).read_bytes()).hexdigest() == h for p, h in snapshot.items())

quote = "“冻结 Q1-D-v2-candidate，并进入 Q2 候选准备，做到 A，不运行实验。”"
state["revision"] = 20
state["stage"] = "FROZEN"
state["execution_status"] = "WAITING"
state["pending_gate"] = None
state["questions"]["Q1"].update({"status": "FROZEN", "validity": "VALID", "frozen_version": "Q1-D-v2-candidate"})
state["questions"]["Q1"]["snapshots"]["Q1-D-v2-candidate"] = snapshot
state["authorizations"].append({
    "id": "U011", "from_stage": "WAIT_D", "to_stage": "FROZEN", "scope": "Q1",
    "plan_version": "Q1-D-v2-candidate", "user_quote": quote,
    "message_ref": "当前任务用户最新明确冻结并进入Q2消息", "confirmed_by": "user", "recorded_date": "2026-09-07",
    "boundary": "冻结Q1-D-v2-candidate的现有证据和输出；不允许覆盖冻结文件。该消息同时另行授权随后进入Q2候选准备到A。"
})
state["history"].append({
    "date": "2026-09-07", "from_stage": "WAIT_D", "to_stage": "FROZEN", "authorization_id": "U011",
    "reason": f"用户明确冻结Q1-D-v2-candidate；记录{len(snapshot)}个文件哈希及五项限制。冻结授权不等于逐项人工复算。",
    "artifacts": ["questions/Q1/freeze_record_Q1-D-v2-candidate.json", "questions/Q1/snapshot_Q1-D-v2-candidate.json"]
})
(project / "state/proposed.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
