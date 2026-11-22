"""Inspect the two recorded Harbor 0.26 control results and synthetic costs."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.harbor import inspect_harbor_job


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class InspectHarborTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "job"
        self.root.mkdir()
        self.trial_dir = self.root / "one-trial"
        self.trial_dir.mkdir()
        self.path = self.trial_dir / "result.json"
        self.path.write_bytes((FIXTURES / "harbor-026-oracle.json").read_bytes())
        (self.root / "result.json").write_text(json.dumps({"n_total_trials": 1}))

    def test_real_harbor_control_cost_is_unavailable(self):
        result = inspect_harbor_job(self.root)
        self.assertTrue(result["complete"])
        self.assertEqual(result["observed_trials"], 1)
        self.assertFalse(result["billing_verified"])
        trial = result["trials"][0]
        self.assertEqual(trial["outcome"], "pass")
        self.assertEqual(trial["agent"], "oracle")
        self.assertIsNone(trial["agent_reported_cost_usd"])
        self.assertEqual(trial["cost_status"], "unavailable")
        self.assertEqual(len(trial["raw_result_sha256"]), 64)

    def test_incomplete_job_explicit(self):
        (self.root / "result.json").write_text(json.dumps({"n_total_trials": 2}))
        self.assertFalse(inspect_harbor_job(self.root)["complete"])

    def test_agent_reported_cost_not_invoice(self):
        trial = json.loads(self.path.read_text())
        trial["agent_result"]["cost_usd"] = 0.123
        self.path.write_text(json.dumps(trial))
        result = inspect_harbor_job(self.root)
        self.assertEqual(result["trials"][0]["agent_reported_cost_usd"], "0.123000000000")
        self.assertEqual(result["trials"][0]["cost_status"], "agent_reported_estimate")
        self.assertFalse(result["billing_verified"])

    def test_negative_cost_refused(self):
        trial = json.loads(self.path.read_text())
        trial["agent_result"]["cost_usd"] = -1
        self.path.write_text(json.dumps(trial))
        with self.assertRaisesRegex(ReceiptError, "negative"):
            inspect_harbor_job(self.root)

    def test_bad_reward_refused(self):
        trial = json.loads(self.path.read_text())
        trial["verifier_result"]["rewards"]["reward"] = float("nan")
        self.path.write_text(json.dumps(trial))
        with self.assertRaisesRegex(ReceiptError, "invalid verifier reward"):
            inspect_harbor_job(self.root)

    def test_symlink_job_refused(self):
        link = self.root.parent / "alias"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ReceiptError, "symlink"):
            inspect_harbor_job(link)

    def test_tiny_positive_cost_cannot_round_to_zero(self):
        trial = json.loads(self.path.read_text())
        trial["agent_result"]["cost_usd"] = "0.0000000000001"
        self.path.write_text(json.dumps(trial))
        with self.assertRaisesRegex(ReceiptError, "positive agent cost"):
            inspect_harbor_job(self.root)

    def test_one_pico_dollar_is_preserved(self):
        trial = json.loads(self.path.read_text())
        trial["agent_result"]["cost_usd"] = "0.000000000001"
        self.path.write_text(json.dumps(trial))
        self.assertEqual(inspect_harbor_job(self.root)["trials"][0]["agent_reported_cost_usd"],
                         "0.000000000001")

    def test_extreme_cost_exponents_fail_with_domain_error(self):
        for value in ("1e1000", "1e-1000", "1" * 65):
            with self.subTest(value=value[:20]):
                trial = json.loads(self.path.read_text())
                trial["agent_result"]["cost_usd"] = value
                self.path.write_text(json.dumps(trial))
                with self.assertRaises(ReceiptError):
                    inspect_harbor_job(self.root)


if __name__ == "__main__":
    unittest.main()
