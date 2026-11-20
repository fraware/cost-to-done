"""Fail-closed tests for single-trial Harbor/gateway receipt assembly."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError, read_trials
from cost_to_done.evidence import EvidenceRequest, inspect_evidence, write_evidence_receipt
from cost_to_done.gateway import PriceSchedule
from cost_to_done.ledger import BudgetLedger


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        task = self.root / "task"
        (task / "tests").mkdir(parents=True)
        (task / "environment").mkdir(parents=True)
        (task / "tests" / "test_state.py").write_text("assert True\n")
        (task / "environment" / "Dockerfile").write_text("FROM python:3.12\n")
        price = PriceSchedule("test-model-1", "2026-11-20", "https://example.com/rates", "20", "40")
        rates = self.root / "price.json"
        rates.write_text(json.dumps(vars(price)))
        self.ledger_path = self.root / "gateway.sqlite3"
        ledger = BudgetLedger(self.ledger_path, budget_usd="5")
        ledger.bind_schedule(price.digest)
        ledger.reserve("request-one", "0.9")
        ledger.settle("request-one", "0.018")
        ledger.reserve("request-two", "0.9")
        ledger.settle("request-two", "0.0056")
        self.request = EvidenceRequest(
            job=self.root / "job", ledger=self.ledger_path, task=task,
            verifier=task / "tests" / "test_state.py", price_schedule=rates,
            configuration_id="pi+mock", agent="pi", model="openai/test-model-1",
            harness_digest="c" * 64, harbor_task_checksum="b" * 40,
        )
        self.fake_job = {
            "complete": True, "observed_trials": 1,
            "trials": [{
                "id": "trial-1", "task": "allocation-repair", "task_checksum": "b" * 40,
                "agent": "pi", "model": "test-model-1", "provider": "openai",
                "outcome": "pass", "elapsed_seconds": 23.5,
                "raw_result_sha256": "a" * 64,
            }],
        }

    def check(self, request=None):
        with patch("cost_to_done.evidence.inspect_harbor_job", return_value=self.fake_job):
            return inspect_evidence(request or self.request)

    def test_passed_multi_request_trial_is_one_attempt(self):
        receipt, evidence = self.check()
        self.assertEqual(receipt["attempts"], [{
            "cost_usd": "0.0236", "seconds": 23.5, "outcome": "pass",
            "cost_source": "rate_card_estimate",
        }])
        self.assertEqual(evidence["gateway_request_count"], 2)
        self.assertFalse(evidence["billing_verified"])
        self.assertEqual(evidence["request_to_trial_attribution"],
                         "single-dedicated-ledger-operator-assertion")

    def test_rejects_incomplete_or_multiple_harbor_trials(self):
        for field, value in (("complete", False), ("observed_trials", 2)):
            original = self.fake_job[field]
            self.fake_job[field] = value
            try:
                with self.assertRaises(ReceiptError):
                    self.check()
            finally:
                self.fake_job[field] = original

    def test_rejects_mismatched_model_and_task_checksum(self):
        for field, value in (("provider", "anthropic"), ("model", "unknown"),
                             ("task_checksum", "d" * 40), ("agent", "other")):
            original = self.fake_job["trials"][0][field]
            self.fake_job["trials"][0][field] = value
            try:
                with self.assertRaises(ReceiptError):
                    self.check()
            finally:
                self.fake_job["trials"][0][field] = original

    def test_rejects_unsettled_request(self):
        ledger = BudgetLedger(self.ledger_path)
        ledger.reserve("undetermined", "1")
        ledger.mark_uncertain("undetermined")
        with self.assertRaisesRegex(ReceiptError, "unresolved liability"):
            self.check()

    def test_rejects_price_and_harness_mismatch(self):
        with self.assertRaises(ReceiptError):
            self.check(replace(self.request, harness_digest="not-a-hash"))
        with self.assertRaises(ReceiptError):
            self.check(replace(self.request, model="openai/another-model"))
        different = PriceSchedule("test-model-1", "2026-11-20", "https://example.com/rates", "21", "40")
        self.request.price_schedule.write_text(json.dumps(vars(different)))
        with self.assertRaisesRegex(ReceiptError, "digests differ"):
            self.check()

    def test_refuses_verifier_symlink_or_external_file(self):
        other = self.root / "external.py"
        other.write_text("assert True\n")
        with self.assertRaisesRegex(ReceiptError, "within"):
            self.check(replace(self.request, verifier=other))
        link = self.request.task / "tests" / "linked.py"
        link.symlink_to(other)
        with self.assertRaisesRegex(ReceiptError, "symlinks"):
            self.check(replace(self.request, verifier=link))

    def test_exports_valid_receipt_and_provenance_once(self):
        dest = self.root / "out" / "trial.jsonl"
        with patch("cost_to_done.evidence.inspect_harbor_job", return_value=self.fake_job):
            info = write_evidence_receipt(self.request, dest)
            with self.assertRaisesRegex(ReceiptError, "already exists"):
                write_evidence_receipt(self.request, dest)
        rows = read_trials(dest)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trial_id, "trial-1")
        meta = json.loads(Path(info["evidence"]).read_text())
        self.assertEqual(meta["price_schedule_sha256"], PriceSchedule.load(self.request.price_schedule).digest)
        self.assertEqual(meta["gateway_request_count"], 2)
        self.assertEqual(meta["harbor_trial_raw_sha256"], "a" * 64)


if __name__ == "__main__":
    unittest.main()
