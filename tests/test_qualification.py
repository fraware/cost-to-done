"""Tests for local task controls and Harbor control evidence validation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_harbor_controls import control_result
from scripts.qualify_task import qualify


TASK = Path(__file__).resolve().parents[1] / "tasks" / "allocation-repair"


class LocalQualificationTests(unittest.TestCase):
    def test_task_has_failing_starter_and_passing_oracle(self):
        evidence = qualify(TASK)
        self.assertEqual(evidence["baseline"], "fail")
        self.assertEqual(evidence["reference"], "pass")
        for key in ("starter_sha256", "verifier_sha256", "oracle_script_sha256"):
            self.assertEqual(len(evidence[key]), 64)


class HarborControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.job = Path(temp.name)
        self.trial = self.job / "trials" / "first" / "result.json"
        self.trial.parent.mkdir(parents=True)
        self.record = {
            "agent_info": {"name": "oracle"},
            "verifier_result": {"rewards": {"reward": 1.0}},
            "exception_info": None,
            "task_checksum": "task-hash",
            "task_name": "allocation-repair",
            "started_at": "2026-11-20T00:00:00+00:00",
            "finished_at": "2026-11-20T00:00:02+00:00",
        }

    def save(self):
        self.trial.write_text(json.dumps(self.record), encoding="utf-8")

    def test_valid_oracle(self):
        self.save()
        self.assertEqual(control_result(self.job, "oracle", 1)["reward"], "1.0")

    def test_invalid_agent_fails(self):
        self.save()
        with self.assertRaisesRegex(ValueError, "expected agent"):
            control_result(self.job, "nop", 0)

    def test_ungraded_control_fails(self):
        self.record["verifier_result"] = None
        self.save()
        with self.assertRaisesRegex(ValueError, "rewards"):
            control_result(self.job, "oracle", 1)

    def test_infrastructure_error_fails(self):
        self.record["exception_info"] = {"exception_type": "AgentTimeoutError"}
        self.save()
        with self.assertRaisesRegex(ValueError, "exception"):
            control_result(self.job, "oracle", 1)


if __name__ == "__main__":
    unittest.main()
