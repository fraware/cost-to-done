"""No-network tests of the one-trial Harbor launch and evidence boundary."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.execute import Launch, _task_hash, execute, plan

TASK = Path(__file__).resolve().parents[1] / "tasks" / "allocation-repair"


class LaunchTests(unittest.TestCase):
    """Check that dry runs never execute providers and invalid plans fail early."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launch = Launch(TASK, self.root / "jobs", "openai/test-model")

    def test_dry_run_has_no_inference_or_secrets(self):
        with patch("cost_to_done.execute._check_prerequisites", side_effect=AssertionError("network path")):
            report = plan(self.launch)
        self.assertEqual(report["status"], "dry_run_only")
        self.assertFalse(report["max_dollar_spend_enforced"])
        self.assertEqual(report["credentials_required_env"], "OPENAI_API_KEY")
        self.assertEqual(report["command"].count("--n-attempts"), 1)
        self.assertIn("max_turns=10", report["command"])
        self.assertIn("api.openai.com", report["command"])

    def test_explicit_consent_required(self):
        with patch("cost_to_done.execute._check_prerequisites", side_effect=AssertionError("should not run")):
            with self.assertRaisesRegex(ReceiptError, "acknowledge"):
                execute(self.launch)
        self.assertFalse((self.root / "jobs").exists())

    def test_task_hash_changes_with_verifier(self):
        task = self.root / "task"
        for name in ("task.toml", "instruction.md", "environment/Dockerfile", "environment/allocate.py",
                     "tests/test.sh", "tests/test_state.py", "solution/solve.sh"):
            dst = task / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes((TASK / name).read_bytes())
        before = _task_hash(task)
        (task / "tests/test_state.py").write_text("# changed verifier")
        self.assertNotEqual(before, _task_hash(task))
        before_oracle = _task_hash(task)
        (task / "solution/solve.sh").write_text("# changed reference only")
        self.assertEqual(before_oracle, _task_hash(task))

    def test_reject_unsafe_model_and_jobs(self):
        for name in ("gpt-x", "openai/../../credentials", "openai/model?key=secret", "openai/model name"):
            with self.subTest(model=name), self.assertRaises(ReceiptError):
                plan(Launch(TASK, self.root / "jobs", name))
        with self.assertRaises(ReceiptError):
            plan(Launch(TASK, TASK / "results", "openai/example"))
        (self.root / "jobs" / "cost-to-done-smoke").mkdir(parents=True)
        with self.assertRaisesRegex(ReceiptError, "already exists"):
            plan(self.launch)

    def test_reject_symlinked_task_artifact(self):
        task = self.root / "task"
        task.mkdir()
        for file in ("task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh"):
            dst = task / file
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text("ok")
        (task / "environment" / "outside").symlink_to("/etc/passwd")
        with self.assertRaisesRegex(ReceiptError, "unsafe task file"):
            plan(Launch(task, self.root / "jobs", "anthropic/model"))

    def test_execute_records_one_real_result_with_estimate_only(self):
        one = {
            "observed_trials": 1, "complete": True, "trials": [{
                "agent": "pi", "model": "test-model", "provider": "openai",
                "agent_reported_cost_usd": "0.004", "outcome": "pass",
                "raw_result_sha256": "a" * 64,
            }],
        }
        with patch("cost_to_done.execute._check_prerequisites"), \
                patch("cost_to_done.execute._run_bounded", return_value=0) as bounded, \
                patch("cost_to_done.execute.inspect_harbor_job", return_value=one):
            evidence = execute(self.launch, acknowledged=True)
        self.assertEqual(evidence["status"], "completed_with_cost_estimate")
        self.assertFalse(evidence["billing_verified"])
        self.assertEqual(bounded.call_count, 1)
        receipt = self.root / "jobs" / "cost-to-done-smoke.execution.json"
        self.assertEqual(json.loads(receipt.read_text())["trial"]["outcome"], "pass")
        if os.name == "posix":
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    def test_failed_agent_does_not_masquerade_as_result(self):
        with patch("cost_to_done.execute._check_prerequisites"), \
                patch("cost_to_done.execute._run_bounded", return_value=1):
            evidence = execute(self.launch, acknowledged=True)
        self.assertEqual(evidence["status"], "harbor_error")
        self.assertNotIn("trial", evidence)

    def test_successful_command_with_missing_trial_is_rejected(self):
        with patch("cost_to_done.execute._check_prerequisites"), \
                patch("cost_to_done.execute._run_bounded", return_value=0), \
                patch("cost_to_done.execute.inspect_harbor_job", return_value={"observed_trials": 0, "complete": False}):
            evidence = execute(self.launch, acknowledged=True)
        self.assertEqual(evidence["status"], "execution_incomplete")
        self.assertIn("exactly one", evidence["error"])


if __name__ == "__main__":
    unittest.main()
