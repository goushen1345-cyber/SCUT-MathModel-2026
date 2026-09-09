import copy
import hashlib
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
version = "Q3-D-v1-candidate"
snapshot_path = project / f"questions/Q3/snapshot_{version}.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
snapshot_doc = json.loads(snapshot_path.read_text(encoding="utf-8"))
if state["revision"] != 37 or state["stage"] != "WAIT_D" or state["active_question"] != "Q3":
    raise SystemExit("Expected revision 37 at Q3 WAIT_D")
if state["pending_gate"].get("plan_version") != version:
    raise SystemExit("Unexpected Q3 D-point version")
for rel, expected in snapshot_doc["files"].items():
    actual = hashlib.sha256((project / rel).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Snapshot mismatch before freeze: {rel}")

snapshot = dict(snapshot_doc["files"])
snapshot[f"questions/Q3/snapshot_{version}.json"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
candidate = copy.deepcopy(state)
candidate["revision"] = 38
candidate["stage"] = "FROZEN"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = None
candidate["authorizations"].append({
    "id": "U021",
    "from_stage": "WAIT_D",
    "to_stage": "FROZEN",
    "scope": "Q3",
    "plan_version": version,
    "user_quote": "冻结 Q3-D-v1-candidate，保留已列限制，不进入论文阶段。",
    "message_ref": "当前任务用户对Q3 D点候选的明确冻结消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "冻结Q3-D-v1-candidate并保留已披露限制；不得进入论文阶段。",
})
candidate["questions"]["Q3"].update({
    "status": "FROZEN",
    "validity": "VALID",
    "frozen_version": version,
})
candidate["questions"]["Q3"]["snapshots"][version] = snapshot
candidate["q3_protocol"].update({
    "status": "FROZEN",
    "frozen_version": version,
    "limitations_preserved": True,
    "paper_stage_authorized": False,
})
candidate["data_scope"]["modeling_authorized"] = "Q1, Q2 and Q3 are frozen; paper stage is not authorized."
candidate["history"].append({
    "date": "2026-09-08",
    "from_stage": "WAIT_D",
    "to_stage": "FROZEN",
    "authorization_id": "U021",
    "reason": "用户明确冻结Q3-D-v1-candidate并保留全部已披露限制；记录Q3证据及快照文档哈希。冻结不表示逐项人工复算，且不进入论文阶段。",
    "artifacts": [
        f"questions/Q3/freeze_record_{version}.json",
        f"questions/Q3/snapshot_{version}.json",
    ],
})
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
