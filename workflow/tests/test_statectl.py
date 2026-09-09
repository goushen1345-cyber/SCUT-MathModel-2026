import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import json

spec = importlib.util.spec_from_file_location("statectl", Path(__file__).parents[1] / "scripts/statectl.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def staged(stage="WAIT_A"):
    s = m.initial(["Q1", "Q2"])
    s.update(stage=stage, active_question="Q1", data_version="data-v1",
             execution_status="WAITING" if stage.startswith("WAIT_") else "ACTIVE")
    s["questions"]["Q1"]["status"] = "ACTIVE"
    if stage.startswith("WAIT_"):
        s["pending_gate"] = dict(id=stage, scope="Q1", plan_version="p1", summary="test fixture",
            allowed_actions=["test"], budget="one run", stop_condition="next gate")
    return s

def advance(s, stage):
    n = copy.deepcopy(s)
    n.update(stage=stage, revision=s["revision"] + 1, pending_gate=None,
             execution_status="WAITING" if stage == "FROZEN" else "ACTIVE")
    n["history"].append({"reason": "synthetic test only"})
    return n

def authorize(s, n, **changes):
    r = dict(id="test-auth", from_stage=s["stage"], to_stage=n["stage"], scope="Q1",
             plan_version="p1", user_quote="SYNTHETIC TEST ONLY", message_ref="test:1", confirmed_by="user")
    r.update(changes)
    n["authorizations"].append(r)

class StateTests(unittest.TestCase):
    def test_initial(self):
        m.validate(m.initial(["Q1"]))
    def test_duplicate_question(self):
        with self.assertRaises(ValueError): m.initial(["Q1", "Q1"])
    def test_missing_approval(self):
        s = staged()
        with self.assertRaises(ValueError): m.check_transition(s, advance(s, "TRIAL"))
    def test_correct_approval(self):
        s = staged(); n = advance(s, "TRIAL"); authorize(s, n)
        m.check_transition(s, n)
    def test_ai_approval(self):
        s = staged(); n = advance(s, "TRIAL"); authorize(s, n, confirmed_by="AI")
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_old_plan(self):
        s = staged(); n = advance(s, "TRIAL"); authorize(s, n, plan_version="old")
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_wrong_scope(self):
        s = staged(); n = advance(s, "TRIAL"); authorize(s, n, scope="Q2")
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_skip(self):
        s = staged(); n = advance(s, "DEEPEN"); authorize(s, n)
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_old_revision(self):
        s = staged(); n = advance(s, "TRIAL"); authorize(s, n); n["revision"] = 0
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_no_question_switch(self):
        s = staged(); n = advance(s, "TRIAL"); n["active_question"] = "Q2"; authorize(s, n)
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_no_early_paper(self):
        s = staged("PAPER")
        with self.assertRaises(ValueError): m.validate(s)
    def test_cycle(self):
        s = m.initial(["Q1", "Q2"])
        s["questions"]["Q1"]["depends_on"] = [{"question": "Q2", "version": None}]
        s["questions"]["Q2"]["depends_on"] = [{"question": "Q1", "version": None}]
        with self.assertRaises(ValueError): m.validate(s)
    def test_dependency_unfrozen(self):
        s = staged(); s["questions"]["Q1"]["depends_on"] = [{"question": "Q2", "version": "v1"}]
        with self.assertRaises(ValueError): m.validate(s)
    def test_core_not_auto_freeze(self):
        s = staged("WAIT_D"); s["questions"]["Q1"]["role"] = "CORE"
        n = advance(s, "FROZEN")
        n["questions"]["Q1"].update(status="FROZEN", frozen_version="v1", snapshots={"v1": {"result.txt": "0" * 64}})
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_hash_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "result.txt").write_text("old")
            s = staged("FROZEN"); s["execution_status"] = "WAITING"
            s["questions"]["Q1"].update(status="FROZEN", frozen_version="v1",
                snapshots={"v1": {"result.txt": hashlib.sha256(b"old").hexdigest()}})
            m.validate(s, root)
            (root / "result.txt").write_text("new")
            with self.assertRaises(ValueError): m.validate(s, root)
    def test_blockers(self):
        s = staged(); s["blockers"] = ["unresolved"]
        with self.assertRaises(ValueError): m.validate(s)
    def test_no_history_rewrite(self):
        s = staged(); s["history"] = [{"original": True}]
        n = advance(s, "TRIAL"); authorize(s, n); n["history"][0] = {}
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_authorized_data_revisit(self):
        s = staged("TRIAL"); n = advance(s, "DATA_PLAN"); n["active_question"] = None
        authorize(s, n, scope="GLOBAL")
        m.check_transition(s, n)
    def test_data_revisit_requires_approval(self):
        s = staged("TRIAL"); n = advance(s, "DATA_PLAN"); n["active_question"] = None
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_wait_gate_data_revisit_new_plan(self):
        s = staged("WAIT_A"); n = advance(s, "DATA_PLAN"); n["active_question"] = None
        authorize(s, n, scope="GLOBAL", plan_version="data-revisit-v1")
        m.check_transition(s, n)
    def test_cannot_freeze_during_trial(self):
        s = staged("TRIAL"); n = advance(s, "TRIAL"); authorize(s, n)
        n["questions"]["Q2"].update(status="FROZEN", frozen_version="v1", snapshots={"v1": {"x": "abc"}})
        with self.assertRaises(ValueError): m.check_transition(s, n)
    def test_complete_lifecycle(self):
        s = m.initial(["Q1"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "result.txt").write_text("synthetic fixture", encoding="utf-8")
            for stage in m.FLOW[1:]:
                n = advance(s, stage)
                if stage == "READY":
                    n["data_version"] = "d1"
                    n["execution_status"] = "WAITING"
                if stage == "CANDIDATES":
                    n["active_question"] = "Q1"
                    n["questions"]["Q1"]["status"] = "ACTIVE"
                if stage.startswith("WAIT_"):
                    n["execution_status"] = "WAITING"
                    n["pending_gate"] = dict(id=stage, plan_version=stage + "-v1",
                        scope="Q1" if stage in m.QUESTION_STAGES else "PAPER" if stage in {"WAIT_P", "WAIT_FINAL"} else "GLOBAL",
                        summary="fixture", allowed_actions=["fixture"], budget="one", stop_condition="next")
                if stage == "FROZEN":
                    n["questions"]["Q1"].update(status="FROZEN", frozen_version="v1",
                        snapshots={"v1": {"result.txt": hashlib.sha256((root / "result.txt").read_bytes()).hexdigest()}})
                if stage == "DONE": n["execution_status"] = "DONE"
                if s["stage"].startswith("WAIT_") or s["stage"] in {"READY", "FROZEN"}:
                    scope = s["pending_gate"]["scope"] if s["pending_gate"] else "Q1"
                    authorize(s, n, id="receipt-" + stage, scope=scope,
                        plan_version=s["pending_gate"]["plan_version"] if s["pending_gate"] else "entry-v1")
                m.check_transition(s, n, root)
                s = n
            self.assertEqual(s["stage"], "DONE")
    def test_cli_commit_and_init_refuses_overwrite(self):
        script = str(Path(m.__file__))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"
            cmd = [sys.executable, script, "init", str(root), "--questions", "Q1"]
            self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            statepath = root / "state/state.json"
            s = m.read(statepath)
            n = advance(s, "WAIT_G0"); n["execution_status"] = "WAITING"
            n["pending_gate"] = dict(id="G0", scope="GLOBAL", plan_version="v1", summary="fixture",
                allowed_actions=["audit"], budget="one", stop_condition="G1")
            candidate = root / "state/proposed.json"
            candidate.write_text(json.dumps(n), encoding="utf-8")
            commit = [sys.executable, script, "commit", str(root), "--candidate", str(candidate)]
            self.assertEqual(subprocess.run(commit, capture_output=True).returncode, 0)
            before = statepath.read_bytes()
            self.assertNotEqual(subprocess.run(commit, capture_output=True).returncode, 0)
            self.assertEqual(before, statepath.read_bytes())

if __name__ == "__main__": unittest.main()
