"""Regression checks for input safety, denominators and comparability."""
from __future__ import annotations

import copy
import unittest
from decimal import Decimal

from cost_to_done.core import ReceiptError, analyze, parse_trial
from cost_to_done.report import render_html

SHA = "a" * 64
OTHER = "b" * 64


def receipt(config: str, task: str, replicate: int = 1, *, cost="0.123456", result="pass"):
    """Construct one explicit end-to-end trial for a controlled comparison."""
    return {
        "trial_id": f"{config}-{task}-{replicate}",
        "configuration_id": config,
        "task_id": task,
        "task_digest": SHA,
        "verifier_digest": SHA,
        "harness_digest": SHA,
        "retry_policy": "restart-on-fail",
        "attempts": [{"cost_usd": cost, "seconds": 1.5, "outcome": result, "cost_source": "billed"}],
    }


class ReceiptTests(unittest.TestCase):
    def test_sum_paid_failures_before_pass(self):
        row = receipt("A", "task")
        row["attempts"] = [
            {"cost_usd": "0.100001", "seconds": 5, "outcome": "fail", "cost_source": "billed"},
            {"cost_usd": "0.100002", "seconds": 3, "outcome": "pass", "cost_source": "billed"},
        ]
        trial = parse_trial(row)
        self.assertTrue(trial.passed)
        self.assertEqual(trial.cost, Decimal("0.200003"))
        self.assertEqual(trial.seconds, 8)

    def test_success_stops_episode(self):
        row = receipt("A", "task")
        row["attempts"].append(row["attempts"][0].copy())
        with self.assertRaisesRegex(ReceiptError, "success"):
            parse_trial(row)

    def test_no_float_costs(self):
        row = receipt("A", "task")
        row["attempts"][0]["cost_usd"] = 0.123
        with self.assertRaisesRegex(ReceiptError, "quoted decimal"):
            parse_trial(row)

    def test_nonfinite_and_scientific_notation_costs_rejected(self):
        for invalid in ("NaN", "Infinity", "-1", "1e999", "1.1234567890123"):
            with self.subTest(value=invalid):
                row = receipt("A", "task")
                row["attempts"][0]["cost_usd"] = invalid
                with self.assertRaises(ReceiptError):
                    parse_trial(row)

    def test_html_escapes_untrusted_names(self):
        row = receipt("<script>alert(1)</script>", "task")
        report = analyze([parse_trial(row)])
        html = render_html(report, title="<img src=x>")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<img src=x>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_no_nan_seconds(self):
        row = receipt("A", "task")
        row["attempts"][0]["seconds"] = float("nan")
        with self.assertRaises(ReceiptError):
            parse_trial(row)

    def test_pooled_cost_includes_failures(self):
        a = parse_trial(receipt("A", "task-1", 1, cost="0.10", result="fail"))
        b = parse_trial(receipt("A", "task-1", 2, cost="0.30", result="pass"))
        result = analyze([a, b])
        self.assertEqual(result["rows"][0]["cost_per_success_usd"], "0.40")
        self.assertEqual(result["rows"][0]["pass_rate"], 0.5)

    def test_zero_success_yields_null_not_zero(self):
        a = parse_trial(receipt("A", "task", result="fail"))
        result = analyze([a])
        self.assertIsNone(result["rows"][0]["cost_per_success_usd"])

    def test_unmatched_tasks_withhold_rank(self):
        a = parse_trial(receipt("A", "task-1"))
        b = parse_trial(receipt("B", "task-2"))
        result = analyze([a, b])
        self.assertFalse(result["eligible_for_ranking"])

    def test_mixed_cost_basis_withholds_rank(self):
        a = receipt("A", "task-1")
        b = receipt("B", "task-1")
        b["attempts"][0]["cost_source"] = "rate_card_estimate"
        result = analyze([parse_trial(a), parse_trial(b)])
        self.assertFalse(result["eligible_for_ranking"])

    def test_verifier_mismatch_rejected(self):
        a = receipt("A", "task-1")
        b = copy.deepcopy(receipt("B", "task-1"))
        b["verifier_digest"] = OTHER
        with self.assertRaisesRegex(ReceiptError, "digests differ"):
            analyze([parse_trial(a), parse_trial(b)])

    def test_same_tasks_with_same_replication_are_comparable(self):
        rows = [parse_trial(receipt(config, task, replica))
                for config in ("A", "B") for task in ("x", "y") for replica in (1, 2)]
        self.assertTrue(analyze(rows)["eligible_for_ranking"])

    def test_bootstrap_reproducible(self):
        rows = [parse_trial(receipt(config, f"t-{idx}", replica,
                                    cost="0.5" if config == "A" else "1.0",
                                    result="pass" if (idx + replica) % 4 else "fail"))
                for config in ("A", "B") for idx in range(5) for replica in (1, 2)]
        first, second = analyze(rows), analyze(rows)
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"][0]["bootstrap_95_usd"]), 2)


if __name__ == "__main__":
    unittest.main()
