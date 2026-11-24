"""Zero-spend negative and positive tests for the historical archive auditor."""
import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.panel import build_panel
from cost_to_done.panel_results import summarize_panel, COMPLETE
from scripts.audit_development_archive import audit, load_json

ROOT = Path(__file__).resolve().parents[1]


class DevelopmentArchiveTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "panel.zip"
        self.plan = build_panel(ROOT, repetitions=3, max_total_usd="18")
        self.records = {}
        self.reference = {"source_commit": "c"*40, "workflow_run_id": 1,
                          "artifact_id": 2, "plan_sha256": self.plan["plan_sha256"],
                          "observations": []}
        for i, trial in enumerate(self.plan["trials"]):
            tid = trial["trial_id"]
            cfg = self.plan["configurations"][trial["configuration"]]
            record = {"trial_id": tid, "plan_sha256": self.plan["plan_sha256"],
                      "model": cfg["model"], "task_fixture": trial["task"],
                      "api": cfg["api"], "reasoning_effort": cfg["reasoning_effort"],
                      "price_schedule_sha256": cfg["price_schedule_sha256"],
                      "provider_invoice_reconciled": False, "provider_spend_limit_verified": False,
                      "verifier_independently_reexecuted": False, "trial_status": COMPLETE,
                      "harbor_trial_outcome": "pass", "harbor_task_checksum": "a"*64,
                      "harbor_raw_result_sha256": f"{i:064x}", "ledger_observed": True,
                      "gateway_rate_card_estimate_usd": "0.001", "gateway_pending": 0,
                      "gateway_uncertain": 0, "gateway_breached": False, "gateway_recorded_calls": 2}
            self.records[tid + ".json"] = record
            self.reference["observations"].append({"trial_id": tid, "status": COMPLETE,
                                                   "verifier": "pass", "rate_card_estimate_usd": "0.001"})
        self.members = {"plan.json": self.plan, "summary.json": summarize_panel(self.plan, list(self.records.values())),
                        **self.records}

    def write_archive(self, members):
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, json.dumps(content))
        self.reference["github_reported_zip_sha256"] = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_complete_archive(self):
        self.write_archive(self.members)
        report, plan, records = audit(self.path, self.plan, self.reference)
        self.assertEqual(len(records), 18)
        self.assertTrue(report["historical_plan_reconstructed"])
        self.assertFalse(report["provider_invoice_reconciled"])
        self.assertEqual(plan, self.plan)

    def test_wrong_hash_extra_member_and_log_disagreement(self):
        self.write_archive(self.members)
        self.reference["github_reported_zip_sha256"] = "0"*64
        with self.assertRaisesRegex(ReceiptError, "ZIP SHA-256"):
            audit(self.path, self.plan, self.reference)
        self.write_archive({**self.members, "../unexpected.json": {}})
        with self.assertRaisesRegex(ReceiptError, "archive members"):
            audit(self.path, self.plan, self.reference)
        members = copy.deepcopy(self.members)
        key = next(iter(self.records))
        members[key]["gateway_rate_card_estimate_usd"] = "0.002"
        self.write_archive(members)
        with self.assertRaisesRegex(ReceiptError, "completed log"):
            audit(self.path, self.plan, self.reference)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ReceiptError):
                load_json(raw)
