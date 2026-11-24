"""Matched fictional accounting, including failure and incomplete support."""
import copy
import tempfile
import unittest
import json
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.repository_comparison import (
    build_comparison_plan, summarize_comparison, render_comparison, SCENARIOS, NETWORK_CHECKS, write_comparison,
)


class RepositoryComparisonTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_comparison_plan("a"*64, "b"*64, "c"*64)
        self.records = []
        for scenario, outcome, char in zip(SCENARIOS, ("fail", "pass"), ("d", "e")):
            self.records.append({
                "scenario": scenario, "plan_sha256": self.plan["plan_sha256"],
                "repository_task_sha256": "a"*64, "qualification_sha256": "b"*64,
                "price_schedule_sha256": "c"*64, "model": "test-model-1", "api": "responses",
                "reasoning_effort": "low", "mock_only": True, "billing_verified": False,
                "repository_execution_scope": "mock_only", "status": "isolated-live-runner-mock-verified",
                "fictional_rate_card_usd": "0.0236", "gateway_calls": 2,
                "verifier_outcome": outcome, "harbor_trial_sha256": char*64,
                "harbor_task_checksum": "f"*64, "network_checks": NETWORK_CHECKS,
                "opaque_reasoning_replay_checked": True,
            })

    def test_complete_and_failed_cost(self):
        summary = summarize_comparison(self.plan, self.records)
        self.assertTrue(summary["complete_matched_accounting"])
        self.assertEqual(summary["known_fictional_total_usd"], "0.0472")
        self.assertIsNone(summary["rows"][0]["fictional_cost_per_completion_usd"])
        self.assertEqual(summary["rows"][1]["fictional_cost_per_completion_usd"], "0.0236")
        self.assertFalse(summary["eligible_for_ranking"])
        self.assertIn("Undefined (zero passes)", render_comparison(self.plan, self.records))

    def test_missing_or_unsettled_withholds_ratios(self):
        summary = summarize_comparison(self.plan, self.records[1:])
        self.assertFalse(summary["complete_matched_accounting"])
        self.assertEqual(summary["rows"][0]["state"], "missing")
        self.assertIsNone(summary["rows"][1]["fictional_cost_per_completion_usd"])
        records = copy.deepcopy(self.records)
        records[0]["status"] = "unresolved"
        summary = summarize_comparison(self.plan, records)
        self.assertEqual(summary["known_fictional_total_usd"], "0.0472")
        self.assertFalse(summary["complete_matched_accounting"])

    def test_identity_mismatch_and_duplicate_rejected(self):
        for field, value in (("mock_only", False), ("plan_sha256", "0"*64),
                             ("harbor_trial_sha256", "e"*64), ("model", "other")):
            records = copy.deepcopy(self.records)
            records[0][field] = value
            with self.subTest(field=field), self.assertRaises(ReceiptError):
                summarize_comparison(self.plan, records)
        records = copy.deepcopy(self.records)
        records[0]["harbor_task_checksum"] = "a"*64
        self.assertFalse(summarize_comparison(self.plan, records)["complete_matched_accounting"])

    def test_report_recomputes_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "plan.json").write_text(json.dumps(self.plan))
            for rec in self.records:
                (root / (rec["scenario"] + ".json")).write_text(json.dumps(rec))
            (root / "summary.json").write_text('{"known_fictional_total_usd":"999"}')
            output = root / "report.html"
            write_comparison(root, output)
            self.assertIn("$0.0472", output.read_text())
            self.assertNotIn("$999", output.read_text())
            with self.assertRaises(ReceiptError):
                write_comparison(root, output)
