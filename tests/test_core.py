"""Regression checks for input safety, denominators and comparability."""
from __future__ import annotations

import copy
import json
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

    def test_different_retry_policies_withhold_monetary_rank(self):
        a = receipt("A", "task-1")
        b = receipt("B", "task-1")
        b["retry_policy"] = "no-retry"
        report = analyze([parse_trial(a), parse_trial(b)])
        self.assertFalse(report["eligible_for_ranking"])
        self.assertTrue(any("Retry policies differ" in warning for warning in report["warnings"]))

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


    def test_single_configuration_is_not_a_ranking(self):
        report = analyze([parse_trial(receipt("A", "task", cost="0.25"))])
        self.assertFalse(report["eligible_for_ranking"])
        self.assertTrue(any("At least two" in w for w in report["warnings"]))
        self.assertIn("<strong>NO</strong>", render_html(report, title="One config"))

    def test_empty_analysis_is_explicitly_rejected(self):
        with self.assertRaisesRegex(ReceiptError, "at least one trial"):
            analyze([])

    def test_sub_cent_model_order_is_exact(self):
        # Both amounts round to the same binary float. The cheaper model's
        # name sorts last alphabetically, exposing a float-based ranking bug.
        expensive = "1000000000.000000000002"
        cheaper = "1000000000.000000000001"
        self.assertEqual(float(expensive), float(cheaper))
        report = analyze([
            parse_trial(receipt("A-expensive", "task", cost=expensive)),
            parse_trial(receipt("Z-cheaper", "task", cost=cheaper)),
        ])
        self.assertTrue(report["eligible_for_ranking"])
        self.assertEqual([r["configuration"] for r in report["rows"]],
                         ["Z-cheaper", "A-expensive"])

    def test_html_displays_nonzero_microcharges_without_rounding(self):
        report = analyze([
            parse_trial(receipt("A", "task", cost="0.000000000002")),
            parse_trial(receipt("B", "task", cost="0.000000000001")),
        ])
        html = render_html(report, title="Microcharge check")
        self.assertIn("$0.000000000001", html)
        self.assertIn("$0.000000000002", html)
        self.assertNotIn("$0.0000</span>", html)

    def test_html_retains_high_precision_large_charges(self):
        report = analyze([
            parse_trial(receipt("A", "task", cost="1000000000.000000000002")),
            parse_trial(receipt("B", "task", cost="1000000000.000000000001")),
        ])
        html = render_html(report, title="Large charge check")
        self.assertIn("$1,000,000,000.000000000001", html)
        self.assertIn("$1,000,000,000.000000000002", html)

    def test_money_formats_zero_and_unbounded_limits(self):
        from cost_to_done.report import _money
        self.assertEqual(_money("0"), "$0.00")
        self.assertEqual(_money("1.2"), "$1.20")
        self.assertEqual(_money("0.000000000001"), "$0.000000000001")
        self.assertEqual(_money(float("inf")), "Unbounded")
        self.assertEqual(_money(None), "Not established")
        with self.assertRaises(ValueError):
            _money(float("nan"))
    def test_zero_success_configurations_are_not_assigned_rank_numbers(self):
        trials = [
            parse_trial(receipt("A", "task", result="fail")),
            parse_trial(receipt("B", "task", result="pass")),
        ]
        report = analyze(trials)
        self.assertFalse(report["eligible_for_ranking"])
        self.assertIsNone(report["rows"][0]["cost_per_success_usd"])
        self.assertIn("—", render_html(report, title="Incomplete evidence"))
        self.assertTrue(any("zero verified successes" in warning for warning in report["warnings"]))

    def test_all_failed_configurations_do_not_produce_winner(self):
        rows = [parse_trial(receipt(c, "task", result="fail")) for c in ("A", "B")]
        report = analyze(rows)
        self.assertFalse(report["eligible_for_ranking"])
        self.assertTrue(all(x["cost_per_success_usd"] is None for x in report["rows"]))

    def test_report_refuses_to_destroy_its_input(self):
        """Using the receipt itself as --output must leave it byte-identical."""
        import tempfile
        from pathlib import Path
        from contextlib import redirect_stderr
        from io import StringIO
        from cost_to_done.cli import main

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "receipts.jsonl"
            source.write_text(json.dumps(receipt("A", "task")) + "\n", encoding="utf-8")
            original = source.read_bytes()
            with redirect_stderr(StringIO()):
                status = main(["report", str(source), "--output", str(source)])
            self.assertEqual(status, 2)
            self.assertEqual(source.read_bytes(), original)

    def test_standard_html_report_private_and_nonoverwriting(self):
        import stat
        import tempfile
        from pathlib import Path
        from cost_to_done.report import write_report

        report = analyze([parse_trial(receipt("A", "task"))])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary.html"
            write_report(report, output, title="Example")
            contents = output.read_bytes()
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaisesRegex(ReceiptError, "already exists"):
                write_report(report, output, title="Another")
            self.assertEqual(output.read_bytes(), contents)

            target = Path(directory) / "source.jsonl"
            target.write_text("private historical trial\n")
            alias = Path(directory) / "alias.html"
            alias.symlink_to(target)
            with self.assertRaisesRegex(ReceiptError, "already exists"):
                write_report(report, alias, title="Example")
            self.assertEqual(target.read_text(), "private historical trial\n")


if __name__ == "__main__":
    unittest.main()
