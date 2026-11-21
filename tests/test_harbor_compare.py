"""Validation, provenance, security and output tests for Harbor-side comparison."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cost_to_done.core import ReceiptError
from cost_to_done.harbor_compare import compare_harbor_jobs, render_harbor_comparison, write_harbor_comparison

SHA = "a" * 64
DIGEST = "b" * 64


def trial(task: str, *, checksum: str = SHA, outcome: str = "pass", cost: str | None = "0.123456789012") -> dict:
    return {
        "task": task, "task_checksum": checksum, "raw_result_sha256": DIGEST,
        "outcome": outcome, "elapsed_seconds": 2.25,
        "agent": "pi", "model": "example-model",
        "agent_reported_cost_usd": cost,
        "cost_status": "agent_reported_estimate" if cost is not None else "unavailable",
    }


def result(*items: dict, complete: bool = True) -> dict:
    return {"complete": complete, "observed_trials": len(items), "trials": list(items)}


class HarborComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.job_a = self.root / "a"
        self.job_b = self.root / "b"
        self.job_a.mkdir()
        self.job_b.mkdir()
        self.snapshots = {
            self.job_a: result(trial("task-1"), trial("task-2", outcome="fail", cost="0.000000000001")),
            self.job_b: result(trial("task-1", outcome="fail", cost="0.4"), trial("task-2", cost="0.2")),
        }
        patch = mock.patch("cost_to_done.harbor_compare._inspect_harbor_job", side_effect=self.fake_inspector)
        patch.start()
        self.addCleanup(patch.stop)

    def fake_inspector(self, job: Path) -> dict:
        return copy.deepcopy(self.snapshots[job])

    def compare(self) -> dict:
        return compare_harbor_jobs([f"small={self.job_a}", f"large={self.job_b}"])

    def test_cli_routes_named_jobs_to_offline_writer(self) -> None:
        """Exercise argparse, exit status and report JSON without provider calls."""
        from contextlib import redirect_stdout
        from io import StringIO
        from cost_to_done.cli import main

        destination = self.root / "cli.html"
        output = StringIO()
        with redirect_stdout(output):
            code = main(["compare-harbor", f"small={self.job_a}", f"large={self.job_b}",
                         "--output", str(destination)])
        self.assertEqual(code, 0)
        self.assertTrue(destination.is_file())
        self.assertFalse(json.loads(output.getvalue())["eligible_for_ranking"])

    def test_matched_jobs_show_all_trials_and_refuse_ranking(self) -> None:
        report = self.compare()
        self.assertEqual(len(report["tasks"]), 2)
        self.assertEqual(report["configurations"][0]["passed"], 1)
        self.assertEqual(report["configurations"][0]["total_agent_reported_estimate_usd"], "0.123456789013")
        self.assertEqual(report["configurations"][1]["total_agent_reported_estimate_usd"], "0.6")
        self.assertFalse(report["eligible_for_ranking"])
        self.assertFalse(report["provider_invoice_reconciled"])
        self.assertFalse(report["independent_verifier_audit"])
        self.assertEqual([x["task"] for x in report["tasks"]], ["task-1", "task-2"])

    def test_unpriced_trial_invalidates_full_total(self) -> None:
        self.snapshots[self.job_a]["trials"][1] = trial("task-2", cost=None)
        report = self.compare()
        self.assertIsNone(report["configurations"][0]["total_agent_reported_estimate_usd"])
        self.assertEqual(report["configurations"][0]["missing_costs"], 1)
        html = render_harbor_comparison(report)
        self.assertIn("Unavailable", html)
        self.assertNotIn("$0.123456789012 <small>estimated total", html)

    def test_mismatched_task_set_rejected(self) -> None:
        self.snapshots[self.job_b]["trials"].pop()
        self.snapshots[self.job_b]["observed_trials"] = 1
        with self.assertRaisesRegex(ReceiptError, "task/checksum mismatch"):
            self.compare()

    def test_mismatched_checksum_rejected(self) -> None:
        self.snapshots[self.job_b]["trials"][0]["task_checksum"] = "c" * 64
        with self.assertRaisesRegex(ReceiptError, "task/checksum mismatch"):
            self.compare()

    def test_duplicate_tasks_rejected(self) -> None:
        self.snapshots[self.job_b]["trials"][1]["task"] = "task-1"
        with self.assertRaisesRegex(ReceiptError, "repeated task"):
            self.compare()

    def test_incomplete_job_rejected(self) -> None:
        self.snapshots[self.job_a]["complete"] = False
        with self.assertRaisesRegex(ReceiptError, "incomplete"):
            self.compare()

    def test_missing_completion_manifest_rejected(self) -> None:
        self.snapshots[self.job_a]["complete"] = None
        with self.assertRaisesRegex(ReceiptError, "incomplete"):
            self.compare()

    def test_zero_or_invalid_cost_metadata_rejected(self) -> None:
        for value in ("-1", "NaN", "1e12", "0.0000000000001", 0.5, "", "1,000"):
            with self.subTest(value=value):
                self.snapshots[self.job_a]["trials"][0]["agent_reported_cost_usd"] = value
                with self.assertRaises(ReceiptError):
                    self.compare()

    def test_cost_status_inconsistent_rejected(self) -> None:
        self.snapshots[self.job_a]["trials"][0]["cost_status"] = "billed"
        with self.assertRaisesRegex(ReceiptError, "provenance"):
            self.compare()

    def test_infrastructure_error_visible_as_separate_outcome(self) -> None:
        self.snapshots[self.job_a]["trials"][0]["outcome"] = "infrastructure_error"
        report = self.compare()
        self.assertEqual(report["configurations"][0]["infrastructure_errors"], 1)
        self.assertEqual(report["configurations"][0]["passed"], 0)

    def test_untrusted_html_is_escaped(self) -> None:
        malicious = "<script>alert(1)</script>"
        self.snapshots[self.job_a]["trials"][0]["task"] = malicious
        self.snapshots[self.job_b]["trials"][0]["task"] = malicious
        html = render_harbor_comparison(self.compare(), title="<svg onload=alert(1)>")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<svg onload=alert(1)>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script src=", html)

    def test_named_specs_unique_and_valid(self) -> None:
        for values in ([f"one={self.job_a}"],
                       [f"one={self.job_a}", f"one={self.job_b}"],
                       [f"../bad={self.job_a}", f"ok={self.job_b}"],
                       [f"a={self.job_a}", f"b={self.job_a}"],
                       ["missing-equals", f"ok={self.job_b}"]):
            with self.subTest(values=values), self.assertRaises(ReceiptError):
                compare_harbor_jobs(values)

    def test_missing_or_symlink_job_rejected(self) -> None:
        alias = self.root / "alias"
        alias.symlink_to(self.job_a, target_is_directory=True)
        with self.assertRaisesRegex(ReceiptError, "real directory"):
            compare_harbor_jobs([f"a={alias}", f"b={self.job_b}"])

    def test_output_is_private_and_original_jobs_untouched(self) -> None:
        input_file = self.job_a / "result.json"
        input_file.write_text("historical job marker")
        output = self.root / "report.html"
        meta = write_harbor_comparison([f"a={self.job_a}", f"b={self.job_b}"], output)
        self.assertTrue(output.is_file())
        self.assertFalse(output.stat().st_mode & 0o077)
        self.assertEqual(input_file.read_text(), "historical job marker")
        self.assertFalse(meta["eligible_for_ranking"])
        self.assertEqual(len(meta["sha256"]), 64)
        with self.assertRaisesRegex(ReceiptError, "already exists"):
            write_harbor_comparison([f"a={self.job_a}", f"b={self.job_b}"], output)

    def test_output_inside_existing_job_rejected(self) -> None:
        with self.assertRaisesRegex(ReceiptError, "outside original"):
            write_harbor_comparison([f"a={self.job_a}", f"b={self.job_b}"], self.job_a / "new.html")

    def test_output_symlink_rejected_without_clobbering_target(self) -> None:
        target = self.root / "existing.txt"
        target.write_text("keep")
        link = self.root / "overview.html"
        link.symlink_to(target)
        with self.assertRaisesRegex(ReceiptError, "already exists"):
            write_harbor_comparison([f"a={self.job_a}", f"b={self.job_b}"], link)
        self.assertEqual(target.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
