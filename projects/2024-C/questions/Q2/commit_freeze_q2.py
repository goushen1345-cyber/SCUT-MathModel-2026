import copy
import hashlib
import json
from pathlib import Path


project = Path(__file__).resolve().parents[2]
state_path = project / "state/state.json"
candidate_path = project / "state/proposed.json"
snapshot_path = project / "questions/Q2/snapshot_Q2-D-v1-candidate.json"
state = json.loads(state_path.read_text(encoding="utf-8"))
snapshot_doc = json.loads(snapshot_path.read_text(encoding="utf-8"))
if state["revision"] != 28 or state["stage"] != "WAIT_D":
    raise SystemExit("Expected revision 28 at WAIT_D")
for rel, expected in snapshot_doc["files"].items():
    actual = hashlib.sha256((project / rel).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Snapshot mismatch before freeze: {rel}")

snapshot = dict(snapshot_doc["files"])
snapshot["questions/Q2/snapshot_Q2-D-v1-candidate.json"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
candidate = copy.deepcopy(state)
candidate["revision"] = 29
candidate["stage"] = "FROZEN"
candidate["execution_status"] = "WAITING"
candidate["pending_gate"] = None
candidate["authorizations"].append({
    "id": "U016",
    "from_stage": "WAIT_D",
    "to_stage": "FROZEN",
    "scope": "Q2",
    "plan_version": "Q2-D-v1-candidate",
    "user_quote": "冻结 Q2-D-v1-candidate，并进入 Q3 候选准备，做到 A，不运行实验。",
    "message_ref": "当前任务用户明确冻结Q2并进入Q3的消息",
    "confirmed_by": "user",
    "recorded_date": "2026-09-08",
    "boundary": "冻结Q2-D-v1-candidate及84份证据文件和快照文档；保留销量、销售规则、随机分布、求解gap和严格豆类诊断限制。该授权同时包含随后单独进入Q3候选准备。",
})
candidate["questions"]["Q2"].update({
    "status": "FROZEN",
    "validity": "VALID",
    "frozen_version": "Q2-D-v1-candidate",
})
candidate["questions"]["Q2"]["snapshots"]["Q2-D-v1-candidate"] = snapshot
candidate["q2_protocol"]["status"] = "FROZEN"
candidate["q2_protocol"]["frozen_version"] = "Q2-D-v1-candidate"
candidate["history"].append(
    {
        "date": "2026-09-08",
        "from_stage": "WAIT_D",
        "to_stage": "FROZEN",
        "authorization_id": "U016",
        "reason": "用户明确冻结Q2-D-v1-candidate；记录84份Q2证据文件和快照文档哈希，保留五项限制。冻结不表示逐项人工复算。",
        "artifacts": [
            "questions/Q2/freeze_record_Q2-D-v1-candidate.json",
            "questions/Q2/snapshot_Q2-D-v1-candidate.json",
        ],
    }
)
candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
