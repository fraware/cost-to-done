"""Panel aggregation: no invented observations or success-only selection."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.panel import build_panel
from cost_to_done.panel_results import summarize_panel, COMPLETE
from scripts.run_development_panel import execute_panel

ROOT = Path(__file__).resolve().parents[1]


class PanelResultTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_panel(ROOT)
        self.records = []
        for index, t in enumerate(self.plan["trials"]):
            config = self.plan["configurations"][t["configuration"]]
            self.records.append({
                "trial_id": t["trial_id"], "plan_sha256": self.plan["plan_sha256"],
                "model": config["model"], "task_fixture": t["task"],
                "api": config["api"], "reasoning_effort": config["reasoning_effort"],
                "price_schedule_sha256": config["price_schedule_sha256"],
                "provider_invoice_reconciled": False, "provider_spend_limit_verified": False,
                "verifier_independently_reexecuted": False, "trial_status": COMPLETE,
                "harbor_trial_outcome": "pass", "harbor_task_checksum": "a"*64,
                "harbor_raw_result_sha256": f"{index:064x}", "ledger_observed": True,
                "gateway_rate_card_estimate_usd": "0.02", "gateway_pending": 0,
                "gateway_uncertain": 0, "gateway_breached": False,
                "gateway_recorded_calls": 2,
            })

    def test_all_costs_including_failures(self):
        self.records[0]["harbor_trial_outcome"] = "fail"
        result = summarize_panel(self.plan, self.records)
        self.assertTrue(result["complete_matched_accounting"])
        self.assertFalse(result["eligible_for_ranking"])
        row = next(r for r in result["rows"] if r["failed"])
        self.assertEqual(row["known_rate_card_estimate_usd"], "0.06")
        self.assertEqual(row["cost_per_verified_completion_usd"], "0.03")

    def test_missing_and_uncertain_block_ratios(self):
        self.records[0]["gateway_uncertain"] = 1
        result = summarize_panel(self.plan, self.records[:-1])
        self.assertFalse(result["complete_matched_accounting"])
        self.assertEqual(sum(r["missing"] for r in result["rows"]), 1)
        self.assertEqual(sum(r["unresolved"] for r in result["rows"]), 1)
        self.assertTrue(all(r["cost_per_verified_completion_usd"] is None for r in result["rows"]))

    def test_duplicate_wrong_plan_and_checksum(self):
        with self.assertRaises(ReceiptError):
            summarize_panel(self.plan, self.records + self.records[:1])
        altered = copy.deepcopy(self.records)
        altered[0]["plan_sha256"] = "c"*64
        with self.assertRaises(ReceiptError):
            summarize_panel(self.plan, altered)
        altered = copy.deepcopy(self.records)
        altered[0]["harbor_raw_result_sha256"] = altered[1]["harbor_raw_result_sha256"]
        with self.assertRaises(ReceiptError):
            summarize_panel(self.plan, altered)
        altered = copy.deepcopy(self.records)
        altered[0]["harbor_task_checksum"] = "c"*64
        self.assertFalse(summarize_panel(self.plan, altered)["complete_matched_accounting"])

    def test_execute_stops_on_unknown_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "panel"
            with patch("scripts.run_development_panel.execute_live", return_value={
                "status": "incomplete_or_uncertain"}) as run:
                result = execute_panel(ROOT, output, Path(tmp) / "fake-key", self.plan)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(sum(r["missing"] for r in result["rows"]), 5)
            self.assertEqual(sum(r["unresolved"] for r in result["rows"]), 1)
            self.assertTrue((output / "summary.json").is_file())

    def test_rehashed_unmatched_plan_is_rejected(self):
        from cost_to_done.panel import _canonical, _sha
        altered = copy.deepcopy(self.plan)
        altered["trials"].pop()
        altered["planned_trial_count"] -= 1
        altered["estimated_admission_total_usd"] = "5"
        altered.pop("plan_sha256")
        altered["plan_sha256"] = _sha(_canonical(altered))
        with self.assertRaises(ReceiptError):
            summarize_panel(altered, [])

    def test_html_report_includes_missing_and_recomputes_summary(self):
        import json
        from cost_to_done.panel_report import render_panel, write_panel_report
        report = render_panel(self.plan, self.records[:-1])
        self.assertIn("Incomplete accounting", report)
        self.assertIn("Missing trials are not zero-cost trials", report)
        self.assertIn("Not established", report)
        self.assertIn("No model ranking", report)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "plan.json").write_text(json.dumps(self.plan))
            (directory / "summary.json").write_text('{"complete_matched_accounting":true}')
            for record in self.records[:-1]:
                (directory / (record["trial_id"] + ".json")).write_text(json.dumps(record))
            output = directory / "report.html"
            write_panel_report(directory, output)
            self.assertEqual(output.read_text(), report)
            with self.assertRaises(ReceiptError):
                write_panel_report(directory, output)
