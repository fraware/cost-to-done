"""Fail-closed tests of direct Harbor reporting and financial completeness."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.harbor_report import (
    _usd, render_harbor_overview, write_harbor_overview,
)
from decimal import Decimal


class HarborReportTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "id": "trial-one", "task": "code/allocation", "agent": "pi",
            "task_checksum": "a" * 64, "raw_result_sha256": "b" * 64,
            "model": "test-model", "provider": "openai", "outcome": "pass",
            "elapsed_seconds": 42.5, "cost_status": "agent_reported_estimate",
            "agent_reported_cost_usd": "0.001230000000",
        }
        self.job = {"job": "example", "observed_trials": 1,
                    "expected_trials": 1, "complete": True, "billing_verified": False,
                    "trials": [self.row]}

    def test_complete_cost_report_unranked(self):
        result = render_harbor_overview(self.job, title="Example run")
        self.assertIn("Example run", result)
        self.assertIn("$0.00123", result)
        self.assertIn("Trial roster complete".upper(), result)
        self.assertIn("Unranked", result)
        self.assertIn("not invoices", result)
        self.assertNotIn("<script", result)
        self.assertNotIn("https://", result)
        self.assertIn("noindex,nofollow", result)
        self.assertIn("b" * 64, result)

    def test_never_loses_micro_and_picodollars(self):
        self.assertEqual(_usd(Decimal("0.000000000001")), "$0.000000000001")
        self.assertEqual(_usd(Decimal("1000.000000000001")), "$1000.000000000001")
        self.assertEqual(_usd(Decimal("1000")), "$1000")
        self.assertEqual(_usd(Decimal("0")), "$0")

    def test_missing_cost_makes_job_total_unavailable(self):
        second = {**self.row, "id": "trial-two", "outcome": "fail",
                  "agent_reported_cost_usd": None, "cost_status": "unavailable"}
        self.job.update({"observed_trials": 2, "expected_trials": 2, "trials": [self.row, second]})
        result = render_harbor_overview(self.job)
        self.assertIn("Unavailable", result)
        self.assertIn("COST EVIDENCE INCOMPLETE", result)
        self.assertNotIn("<strong>$0.00123</strong>", result)
        self.assertIn("No cost data", result)

    def test_incomplete_job_declared_not_complete(self):
        self.job["complete"] = False
        result = render_harbor_overview(self.job)
        self.assertIn("TRIAL ROSTER UNCONFIRMED", result)
        self.assertNotIn("TRIAL ROSTER COMPLETE", result)

    def test_escapes_untrusted_fields(self):
        self.row["task"] = "</td><script>alert(1)</script>"
        self.row["agent"] = 'agent" onclick="evil()'
        self.row["id"] = '" onmouseover="alert(1)'
        result = render_harbor_overview(self.job, title="<script>evil</script>")
        self.assertNotIn("<script>", result)
        self.assertNotIn('onclick="evil()"', result)
        self.assertNotIn('onmouseover="alert(1)"', result)
        self.assertIn("&lt;script&gt;", result)

    def test_zero_passes_do_not_create_cost_per_success(self):
        self.row["outcome"] = "fail"
        result = render_harbor_overview(self.job)
        self.assertIn("Reported passes", result)
        self.assertIn("$0.00123", result)
        self.assertNotIn("cost per success", result.lower())

    def test_error_outcome_is_separate_from_failure(self):
        self.row["outcome"] = "infrastructure_error"
        result = render_harbor_overview(self.job)
        self.assertIn("INFRA ERROR", result)
        self.assertIn("1 infrastructure errors", result)

    def test_rejects_bad_counts_and_duplicate_ids(self):
        self.job["observed_trials"] = 2
        with self.assertRaisesRegex(ReceiptError, "count mismatch"):
            render_harbor_overview(self.job)
        self.job["trials"] = [self.row, self.row]
        with self.assertRaisesRegex(ReceiptError, "repeated"):
            render_harbor_overview(self.job)

    def test_rejects_nonfinite_and_negative_prices(self):
        for value in ("NaN", "-1", "Infinity", "1e1000", "free"):
            with self.subTest(value=value):
                self.row["agent_reported_cost_usd"] = value
                with self.assertRaises(ReceiptError):
                    render_harbor_overview(self.job)

    def test_rejects_cost_status_mismatch(self):
        self.row["cost_status"] = "unavailable"
        with self.assertRaisesRegex(ReceiptError, "conflicts"):
            render_harbor_overview(self.job)

    def test_rejects_invalid_report_hashes(self):
        self.row["raw_result_sha256"] = "bad"
        with self.assertRaisesRegex(ReceiptError, "SHA-256"):
            render_harbor_overview(self.job)

    def test_rejects_bad_elapsed(self):
        for value in (float("inf"), float("nan"), -10, True, "10"):
            with self.subTest(value=value):
                self.row["elapsed_seconds"] = value
                with self.assertRaisesRegex(ReceiptError, "elapsed"):
                    render_harbor_overview(self.job)

    def test_rejects_bogus_report_title_and_empty_trials(self):
        with self.assertRaises(ReceiptError):
            render_harbor_overview(self.job, title="")
        self.job["trials"] = []
        self.job["observed_trials"] = 0
        with self.assertRaises(ReceiptError):
            render_harbor_overview(self.job)

    def test_write_exclusive_no_modified_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / "harbor-job"
            job.mkdir()
            (job / "result.json").write_text('{"n_total_trials":1}')
            output = root / "local-summary.html"
            with patch("cost_to_done.harbor_report.inspect_harbor_job", return_value=self.job):
                info = write_harbor_overview(job, output, title="Test")
                self.assertTrue(output.exists())
                self.assertFalse(info["billing_verified"])
                self.assertFalse(info["ranking_generated"])
                self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                self.assertEqual((job / "result.json").read_text(), '{"n_total_trials":1}')
                with self.assertRaisesRegex(ReceiptError, "already exists"):
                    write_harbor_overview(job, output)
                with self.assertRaisesRegex(ReceiptError, "outside"):
                    write_harbor_overview(job, job / "mutate.html")

    def test_rejects_symlink_output_and_job_inside(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = root / "job"
            job.mkdir()
            output = root / "symlink.html"
            output.symlink_to(root / "missing")
            with self.assertRaisesRegex(ReceiptError, "already exists"):
                write_harbor_overview(job, output)

    def test_deterministic_html(self):
        self.assertEqual(render_harbor_overview(self.job), render_harbor_overview(self.job))


    def test_actual_harbor_fixture_and_cli(self):
        """Exercise the real Harbor inspector on the pinned fixture via CLI."""
        from contextlib import redirect_stdout
        from io import StringIO

        from cost_to_done.cli import main
        source = Path(__file__).parent / "fixtures" / "harbor-026-oracle.json"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "job"
            trial = job / "one-trial"
            trial.mkdir(parents=True)
            (trial / "result.json").write_bytes(source.read_bytes())
            (job / "result.json").write_text('{"n_total_trials":1}')
            destination = root / "overview.html"
            output = StringIO()
            with redirect_stdout(output):
                status = main(["report-harbor", str(job), "--output", str(destination)])
            self.assertEqual(status, 0)
            meta = json.loads(output.getvalue())
            self.assertEqual(meta["observed_trials"], 1)
            self.assertFalse(meta["billing_verified"])
            html = destination.read_text()
            self.assertIn("oracle", html)
            self.assertIn("Unavailable", html)
            self.assertIn("PASS", html)
            self.assertIn("Unranked", html)

if __name__ == "__main__":
    unittest.main()
