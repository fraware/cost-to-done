"""Offline archive review tests using explicitly synthetic evidence."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.upstream_pilot import STARTERS, MODELS
from cost_to_done.upstream_replay import MODULES
from cost_to_done.replay import IMAGE, REPLAY_SCRIPT
from scripts.prepare_external_controls import CASES
from scripts.run_upstream_pilot import SCOPE, build_plan
from scripts.audit_upstream_panel import audit, digest, render
from test_upstream_pilot import make_record, token


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(root):
    qualifications = {}
    for task, pin in STARTERS.items():
        case = CASES[task]
        q = {"schema_version": 1, "status": "repository_task_controls_agree",
             "scope": "operator_supplied_local_harbor_nop_controls", "task": task,
             "origin_authenticated": False, "paid_execution_authorized": False,
             "provider_calls": 0, "shared_input_sha256": token(task + "shared")}
        p = {"scope": "public_upstream_development_controls", "task": task,
             "held_out": False, "provider_calls": 0, "paid_execution_authorized": False,
             "upstream_repository": "https://github.com/python/cpython",
             "upstream_issue": case["issue"], "source_path": f"Lib/{case['module']}.py",
             "controls": {}}
        for role, outcome in (("starter", "fail"), ("reference", "pass")):
            commit = token(task + role + "commit")[:40]
            task_digest = pin if role == "starter" else token(task + "reference")
            q[role] = {"outcome": outcome, "git_commit": commit,
                       "task_input_sha256": task_digest,
                       "harbor_raw_result_sha256": token(task + role + "raw"),
                       "harbor_task_checksum": token(task + role + "harbor")}
            p["controls"][role] = {"packaging_commit": commit, "task_input_sha256": task_digest,
                "upstream_commit": case[role][0], "upstream_source_blob": case[role][1],
                "upstream_license_blob": case["license"], "source_sha256": token(task + role + "source"),
                "local_control": {"outcome": outcome, "tests": 4, "failures": int(role == "starter"),
                                  "errors": 0, "skips": 0, "expected_failures": 0,
                                  "unexpected_successes": 0}}
        q["qualification_sha256"] = digest(q)
        qualifications[task] = q["qualification_sha256"]
        write(root / "upstream-controls" / task / "qualification.json", q)
        write(root / "upstream-controls" / task / "provenance.json", p)
    plan = build_plan(qualifications, {m: token(m) for m in MODELS}, "a"*40)
    write(root / "upstream-preflight/plan.json", plan)
    write(root / "upstream-preflight/preflight.json",
          {"scope": SCOPE, "plan_sha256": plan["plan_sha256"], "staged_trials": 16,
           "provider_calls": 0, "paid_execution_authorized": False})
    return plan


def intent(root, plan, index):
    trial = plan["trials"][index]
    write(root / "upstream-paid" / f"{index:02d}.intent.json",
          {"trial_id": trial["id"], "plan_sha256": plan["plan_sha256"], "status": "attempt_intended"})


class ArchiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.plan = fixture(self.root)

    def start_paid(self):
        write(self.root / "upstream-paid/plan.json", self.plan)

    def record(self, index, *, passed=True):
        intent(self.root, self.plan, index)
        row = make_record(self.plan, self.plan["trials"][index], passed=passed)
        write(self.root / "upstream-paid" / f"{index:02d}.json", row)
        return row

    def test_preflight_has_no_paid_observations(self):
        result = audit(self.root)
        self.assertFalse(result["paid_artifact_present"])
        self.assertFalse(result["complete_matched_accounting"])
        self.assertEqual({r["state"] for r in result["trials"]}, {"not_observed"})
        self.assertIn("Preflight only", render(result))
        self.assertTrue(all(r["known_estimate_usd"] is None for r in result["configurations"]))

    def test_full_accounting_ignores_saved_summary(self):
        self.start_paid()
        model = sorted(MODELS)[0]
        for i, trial in enumerate(self.plan["trials"]):
            self.record(i, passed=trial["model"] != model or trial["repetition"] == 1)
        write(self.root / "upstream-paid/summary.json", {"claimed": "not trusted"})
        result = audit(self.root)
        self.assertTrue(result["complete_matched_accounting"])
        self.assertEqual(result["configurations"][0]["cost_per_completion"],
                         {"numerator_usd": "0.08", "denominator": 4})
        self.assertEqual(result["configurations"][1]["cost_per_completion"],
                         {"numerator_usd": "0.08", "denominator": 8})

    def test_interruption_preserves_intent_and_withholds_ratios(self):
        self.start_paid()
        self.record(0)
        intent(self.root, self.plan, 1)
        result = audit(self.root)
        self.assertEqual(result["trials"][1]["state"], "intent_without_observation")
        self.assertEqual(result["trials"][2]["state"], "not_observed")
        self.assertTrue(all(r["cost_per_completion"] is None for r in result["configurations"]))

    def test_reject_nonprefix_and_missing_intent(self):
        self.start_paid()
        self.record(1)
        with self.assertRaises(ReceiptError):
            audit(self.root)
        (self.root / "upstream-paid/01.intent.json").unlink()
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def test_reject_cost_without_ledger(self):
        self.start_paid()
        row = self.record(0)
        row["ledger_observed"] = False
        write(self.root / "upstream-paid/00.json", row)
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def test_reject_duplicate_hash(self):
        self.start_paid()
        first = self.record(0)
        second = self.record(1)
        second["harbor_raw_result_sha256"] = first["harbor_raw_result_sha256"]
        write(self.root / "upstream-paid/01.json", second)
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def test_reject_tampered_source_identity(self):
        task = next(iter(STARTERS))
        path = self.root / "upstream-controls" / task / "provenance.json"
        row = json.loads(path.read_text())
        row["controls"]["starter"]["upstream_source_blob"] = "0"*40
        write(path, row)
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def test_reject_duplicate_json_key(self):
        path = self.root / "upstream-preflight/preflight.json"
        path.write_text('{"scope":"x","scope":"y"}')
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def enable_replay_plan(self):
        self.plan = build_plan(self.plan["qualification_digests"],
                               self.plan["price_schedule_digests"],
                               self.plan["harness_commit"], capture=True)
        write(self.root / "upstream-preflight/plan.json", self.plan)
        write(self.root / "upstream-preflight/preflight.json",
              {"scope": SCOPE, "plan_sha256": self.plan["plan_sha256"],
               "staged_trials": 16, "provider_calls": 0,
               "paid_execution_authorized": False})
        self.start_paid()

    def replay(self, index, row, *, agree=True):
        task = self.plan["trials"][index]["task"]
        expected = row["harbor_trial_outcome"]
        replay = {"task": task, "source_path": MODULES[task],
                  "base_task_input_sha256": STARTERS[task],
                  "harbor_raw_result_sha256": row["harbor_raw_result_sha256"],
                  "candidate_sha256": token(f"candidate-{index}"),
                  "verifier_sha256": hashlib.sha256(CASES[task]["tests"].encode()).hexdigest(),
                  "replay_script_sha256": hashlib.sha256(REPLAY_SCRIPT.replace(
                      "test_state.py", "test_regression.py").encode()).hexdigest(),
                  "image": IMAGE, "network_mode": "none",
                  "provider_credentials_mounted": False,
                  "adversarial_verifier_integrity_established": False,
                  "cleanup_confirmed": True, "independent_process_reexecution": True,
                  "outcome": expected if agree else ("fail" if expected == "pass" else "pass")}
        side = {"trial_id": row["trial_id"], "plan_sha256": self.plan["plan_sha256"],
                "replay": replay, "agreement": agree}
        write(self.root / "upstream-paid" / f"{index:02d}.replay.json", side)
        return side

    def test_all_capture_enabled_trials_agree(self):
        self.enable_replay_plan()
        for i in range(16):
            self.replay(i, self.record(i, passed=i % 3 != 0))
        result = audit(self.root)
        self.assertTrue(result["complete_matched_accounting"])
        self.assertTrue(result["complete_replay_agreement"])
        self.assertEqual(result["replay_agreement_count"], 16)

    def test_missing_replay_stops_prefix(self):
        self.enable_replay_plan()
        self.record(0)
        result = audit(self.root)
        self.assertEqual(result["trials"][0]["replay_state"], "missing")
        self.assertFalse(result["complete_replay_agreement"])
        self.record(1)
        with self.assertRaises(ReceiptError):
            audit(self.root)

    def test_disagreement_and_tampered_binding(self):
        self.enable_replay_plan()
        side = self.replay(0, self.record(0), agree=False)
        result = audit(self.root)
        self.assertEqual(result["trials"][0]["replay_state"], "disagree")
        self.assertFalse(result["complete_replay_agreement"])
        side["replay"]["verifier_sha256"] = "0"*64
        write(self.root / "upstream-paid/00.replay.json", side)
        with self.assertRaises(ReceiptError):
            audit(self.root)
