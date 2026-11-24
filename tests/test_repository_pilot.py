"""Fixed fixture gate and conservative pilot accounting, without inference."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.repository_pilot import trusted_dispatch, validate_fixed_starter, MODELS
from scripts.run_repository_pilot import summarize


class PilotTests(unittest.TestCase):
    def test_dispatch_guard(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "fraware/cost-to-done",
               "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "GITHUB_RUN_ATTEMPT": "1", "CTD_REPOSITORY_PILOT_AUTHORIZED": "1"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(trusted_dispatch())
        for field in env:
            with self.subTest(field=field), patch.dict(os.environ, {**env, field: "invalid"}, clear=True):
                self.assertFalse(trusted_dispatch())

    def test_fixture_exact_bytes(self):
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run([sys.executable, "-m", "scripts.prepare_repository_pilot", str(root)], check=True)
            self.assertEqual(validate_fixed_starter(root / "pilot-starter")["task"], "addition-repair")
            with self.assertRaises(ReceiptError):
                validate_fixed_starter(root / "pilot-reference")
            (root / "pilot-starter/environment/workspace/app/calc.py").write_text("changed")
            with self.assertRaises(ReceiptError):
                validate_fixed_starter(root / "pilot-starter")

    def test_conservative_summary(self):
        models = list(MODELS)
        plan = {"scope": "fixed_public_synthetic_external_repository", "plan_sha256": "a"*64,
                "task_input_sha256": "b"*64,
                "models": [{"model": model, "price_schedule_sha256": "c"*64} for model in models]}
        rows = []
        for model, outcome, raw in zip(models, ("fail", "pass"), ("d"*64, "e"*64)):
            rows.append({"model": model, "plan_sha256": "a"*64, "task_input_sha256": "b"*64,
                         "price_schedule_sha256": "c"*64,
                         "trial_status": "completed_with_unverified_rate_card_estimate",
                         "api": "responses", "reasoning_effort": "low", "mock_only": False,
                         "ledger_observed": True, "provider_invoice_reconciled": False,
                         "provider_spend_limit_verified": False, "verifier_independently_reexecuted": False,
                         "harbor_trial_outcome": outcome, "gateway_pending": 0, "gateway_uncertain": 0,
                         "gateway_breached": False, "gateway_recorded_calls": 2,
                         "gateway_rate_card_estimate_usd": "0.01",
                         "harbor_task_checksum": "f"*64, "harbor_raw_result_sha256": raw})
        report = summarize(plan, rows)
        self.assertTrue(report["complete_matched_accounting"])
        self.assertEqual(report["known_total_estimate_usd"], "0.02")
        self.assertIsNone(report["rows"][0]["cost_per_completion_usd"])
        self.assertEqual(report["rows"][1]["cost_per_completion_usd"], "0.01")
        self.assertFalse(summarize(plan, rows[:1])["complete_matched_accounting"])
        rows[1]["harbor_task_checksum"] = "0"*64
        self.assertFalse(summarize(plan, rows)["complete_matched_accounting"])
        rows[1]["harbor_task_checksum"] = "f"*64
        rows[1]["gateway_uncertain"] = 1
        self.assertFalse(summarize(plan, rows)["complete_matched_accounting"])
