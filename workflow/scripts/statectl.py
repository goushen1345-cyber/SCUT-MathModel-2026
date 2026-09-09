"""Small, standard-library state checker; not a security or scientific validator."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

FLOW = ["GLOBAL", "WAIT_G0", "DATA_PLAN", "WAIT_G1", "DATA_EXEC", "WAIT_G2",
        "READY", "CANDIDATES", "WAIT_A", "TRIAL", "WAIT_B", "DEEPEN_PLAN",
        "WAIT_C", "DEEPEN", "WAIT_D", "FROZEN", "PAPER_PLAN", "WAIT_P",
        "PAPER", "WAIT_FINAL", "DONE"]
EDGES = set(zip(FLOW, FLOW[1:])) | {
    ("WAIT_D", "DEEPEN_PLAN"), ("WAIT_D", "CANDIDATES"),
    ("FROZEN", "CANDIDATES"), ("FROZEN", "DEEPEN_PLAN")}
QUESTION_STAGES = set(FLOW[7:16])
REVISIT_STAGES = QUESTION_STAGES | {"READY", "PAPER_PLAN", "WAIT_P", "PAPER", "WAIT_FINAL"}
EDGES |= {(stage, "DATA_PLAN") for stage in REVISIT_STAGES}

def need(condition, message):
    if not condition:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def initial(names):
    need(bool(names) and len(names) == len(set(names)), "Unique questions required")
    need(all(re.fullmatch(r"Q[1-9][0-9]*", n) for n in names), "Use Q1, Q2, ...")
    return {"schema_version": 1, "revision": 0, "stage": "GLOBAL",
            "execution_status": "ACTIVE", "active_question": None,
            "data_version": None, "pending_gate": None,
            "questions": {n: {"role": "NORMAL", "status": "NOT_STARTED",
                "validity": "VALID", "depends_on": [], "frozen_version": None,
                "snapshots": {}} for n in names},
            "authorizations": [], "history": [], "blockers": []}

def validate(s, root=None):
    need(s["schema_version"] == 1, "Unsupported schema")
    need(type(s["revision"]) is int and s["revision"] >= 0, "Bad revision")
    stage, qs = s["stage"], s["questions"]
    need(stage in FLOW and bool(qs), "Invalid stage/questions")
    need(s["execution_status"] in {"ACTIVE", "WAITING", "BLOCKED", "DONE"}, "Bad status")
    need(not s["blockers"] or s["execution_status"] == "BLOCKED", "Unresolved blockers")
    if s["execution_status"] != "BLOCKED":
        expected = "WAITING" if stage.startswith("WAIT_") or stage in {"READY", "FROZEN"} else "DONE" if stage == "DONE" else "ACTIVE"
        need(s["execution_status"] == expected, "Stage/status mismatch")
    active = s["active_question"]
    need(active is None or active in qs, "Unknown active question")
    if stage in QUESTION_STAGES:
        need(active in qs and s["data_version"], "Question needs active scope and data")
        need(qs[active]["validity"] == "VALID" or s["execution_status"] == "BLOCKED", "Active question stale")
        if stage != "FROZEN":
            need(qs[active]["status"] == "ACTIVE", "Research question must be active")
    if stage.startswith("WAIT_"):
        gate = s["pending_gate"]
        need(isinstance(gate, dict), "Pending gate missing")
        for key in ("id", "plan_version", "scope", "summary", "allowed_actions", "budget", "stop_condition"):
            need(bool(gate.get(key)), "Missing gate field: " + key)
        scope = active if stage in QUESTION_STAGES else "PAPER" if stage in {"WAIT_P", "WAIT_FINAL"} else "GLOBAL"
        need(gate["scope"] == scope, "Wrong gate scope")
    else:
        need(s["pending_gate"] is None, "Unexpected pending gate")
    visited, visiting = set(), set()
    def visit(name):
        need(name not in visiting, "Cyclic question dependencies")
        if name in visited:
            return
        visiting.add(name)
        q = qs[name]
        need(q["role"] in {"NORMAL", "CORE"}, "Invalid role")
        need(q["status"] in {"NOT_STARTED", "ACTIVE", "FROZEN"}, "Invalid question status")
        need(q["validity"] in {"VALID", "STALE"}, "Invalid validity")
        for dep in q["depends_on"]:
            need(dep["question"] in qs, "Unknown dependency")
            visit(dep["question"])
            if q["validity"] == "VALID" and (q["status"] != "NOT_STARTED" or name == active):
                up = qs[dep["question"]]
                need(up["status"] == "FROZEN" and up["validity"] == "VALID", "Dependency not ready")
                need(dep["version"] is not None and dep["version"] == up["frozen_version"], "Dependency version mismatch")
        if q["status"] == "FROZEN":
            version = q["frozen_version"]
            need(version and q["snapshots"].get(version), "Frozen snapshot missing")
            if root and q["validity"] == "VALID":
                base = Path(root).resolve()
                for rel, digest in q["snapshots"][version].items():
                    path = (base / rel).resolve()
                    need(not Path(rel).is_absolute() and base in path.parents, "Unsafe snapshot path")
                    need(path.is_file(), "Snapshot file missing: " + rel)
                    need(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "Snapshot changed: " + rel)
        visiting.remove(name)
        visited.add(name)
    for name in qs:
        visit(name)
    if stage == "FROZEN":
        need(qs[active]["status"] == "FROZEN", "Active question not frozen")
    if stage in {"PAPER_PLAN", "WAIT_P", "PAPER", "WAIT_FINAL", "DONE"}:
        need(all(q["status"] == "FROZEN" and q["validity"] == "VALID" for q in qs.values()), "Paper requires all questions frozen and valid")
    ids = [a["id"] for a in s["authorizations"]]
    need(len(ids) == len(set(ids)), "Duplicate authorization")
    return s

def check_transition(old, new, root=None):
    validate(old)  # Old snapshot may now be stale; check new effective files below.
    validate(new, root)
    need(new["revision"] == old["revision"] + 1, "Stale state revision")
    need(set(old["questions"]) == set(new["questions"]), "Question list changes require separate migration")
    for key in ("authorizations", "history"):
        need(new[key][:len(old[key])] == old[key], "History is append-only: " + key)
    need(len(new["history"]) > len(old["history"]), "Record transition rationale")
    a, b = old["stage"], new["stage"]
    need(a == b or (a, b) in EDGES, "Illegal stage transition")
    changed_q = old["active_question"] != new["active_question"]
    revisit = b == "DATA_PLAN" and a in REVISIT_STAGES
    entering = a in {"READY", "FROZEN"} and b == "CANDIDATES"
    need(not changed_q or entering or (revisit and new["active_question"] is None), "Question switch not allowed")
    need(not (a == "WAIT_D" and b == "FROZEN" and changed_q), "Freeze is not enter-next")
    sensitive = old["data_version"] != new["data_version"] or changed_q
    for name, q in old["questions"].items():
        nq = new["questions"][name]
        for v, manifest in q["snapshots"].items():
            need(nq["snapshots"].get(v) == manifest, "Frozen history cannot be overwritten")
        if q != nq:
            sensitive = True
        if q["status"] == "FROZEN" and nq["status"] != "FROZEN":
            need((a == "FROZEN" and name == old["active_question"] and b in {"CANDIDATES", "DEEPEN_PLAN"})
                 or (entering and name == new["active_question"]), "Reopen needs explicit scoped transition")
        if q["status"] != "FROZEN" and nq["status"] == "FROZEN":
            need(a == "WAIT_D" and b == "FROZEN" and name == old["active_question"], "Only D can freeze active question")
        if old["data_version"] and old["data_version"] != new["data_version"] and q["status"] != "NOT_STARTED":
            need(nq["validity"] == "STALE", "Data change must invalidate prior research")
    gated = (a.startswith("WAIT_") and a != b) or (a == "FROZEN" and a != b) or sensitive or entering or revisit
    if gated:
        scope = "GLOBAL" if revisit else new["active_question"] if changed_q else old["pending_gate"]["scope"] if old["pending_gate"] else old["active_question"] or "GLOBAL"
        matches = [r for r in new["authorizations"][len(old["authorizations"]):]
                   if r.get("from_stage") == a and r.get("to_stage") == b and r.get("scope") == scope]
        need(bool(matches), "Explicit scoped authorization required")
        receipt = matches[-1]
        for key in ("id", "plan_version", "user_quote", "message_ref"):
            need(isinstance(receipt.get(key), str) and receipt[key].strip(), "Missing authorization evidence: " + key)
        need(receipt.get("confirmed_by") == "user", "AI cannot approve")
        if old["pending_gate"] and not revisit:
            need(receipt["plan_version"] == old["pending_gate"]["plan_version"], "Approval for wrong plan version")
    if a == b and a.startswith("WAIT_") and new["pending_gate"] != old["pending_gate"]:
        need(new["pending_gate"]["plan_version"] != old["pending_gate"]["plan_version"], "Changed plan needs new version")
    return new

def atomic_write(path, content):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def render(root, s):
    content = "# 当前状态（自动视图）\n\n" + "\n".join(
        f"- {k}: {s[k]}" for k in ("revision", "stage", "execution_status", "active_question", "data_version"))
    content += "\n\n正式依据是 state.json；此文件不是人工授权。\n"
    if s["pending_gate"]:
        content += "\n待确认：" + s["pending_gate"]["summary"] + "\n"
    atomic_write(Path(root) / "state/state.md", content)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "validate", "view", "commit"])
    parser.add_argument("project", type=Path)
    parser.add_argument("--questions", nargs="+", default=["Q1", "Q2", "Q3"])
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    root = args.project.resolve()
    path = root / "state/state.json"
    if args.command == "init":
        s = initial(args.questions)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(s, stream, ensure_ascii=False, indent=2)
        for name, title in (("decisions.md", "决策记录"), ("ai_usage_log.md", "AI 使用记录")):
            p = path.parent / name
            if not p.exists():
                with p.open("x", encoding="utf-8") as stream:
                    stream.write("# " + title + "\n\n尚无记录；不得补造人工批准。\n")
        render(root, s)
    elif args.command == "commit":
        need(args.candidate is not None, "--candidate required")
        lock = path.parent / ".state.lock"
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.close(fd)
            s = check_transition(read(path), read(args.candidate), root)
            atomic_write(path, json.dumps(s, ensure_ascii=False, indent=2) + "\n")
            render(root, s)
        finally:
            lock.unlink()
    else:
        s = validate(read(path), root)
        if args.command == "view":
            render(root, s)
    print(json.dumps({"ok": True, "stage": s["stage"], "revision": s["revision"]}, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit("REFUSED: " + str(exc))
