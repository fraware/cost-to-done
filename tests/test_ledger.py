"""Deterministic budget reservation and reconciliation tests; no providers."""
from __future__ import annotations

import concurrent.futures
import os
import tempfile
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.ledger import BudgetLedger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "ledger.db"
        self.ledger = BudgetLedger(self.path, budget_usd="1.00")

    def test_exact_reservation_then_settlement(self):
        self.ledger.reserve("call-1", "0.750000000001")
        self.assertEqual(self.ledger.snapshot().available, "0.249999999999")
        self.assertEqual(self.ledger.settle("call-1", "0.20").available, "0.8")
        self.assertEqual(self.ledger.entries()[0]["actual_usd"], "0.2")

    def test_reservation_denied_before_forwarding(self):
        self.ledger.reserve("request1", "0.9")
        with self.assertRaisesRegex(ReceiptError, "admission denied"):
            self.ledger.reserve("request2", "0.2")
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_uncertain_cost_retains_authorization(self):
        self.ledger.reserve("a", "0.90")
        a = self.ledger.mark_uncertain("a")
        self.assertEqual(a.uncertain, 1)
        self.assertEqual(a.reserved, "0.9")
        with self.assertRaises(ReceiptError):
            self.ledger.reserve("b", "0.2")
        self.ledger.settle("a", "0")
        self.assertEqual(self.ledger.snapshot().available, "1")

    def test_overrun_recorded_as_breach_and_new_spend_blocked(self):
        self.ledger.reserve("a", "0.8")
        self.ledger.settle("a", "1.1")
        summary = self.ledger.snapshot()
        self.assertTrue(summary.breached)
        self.assertEqual(summary.settled, "1.1")
        self.assertEqual(summary.available, "0")
        with self.assertRaises(ReceiptError):
            self.ledger.reserve("b", "0.01")

    def test_per_request_overrun_blocks_future_admission(self):
        self.ledger.reserve("overrun", "0.2")
        status = self.ledger.settle("overrun", "0.3")
        self.assertTrue(status.breached)
        self.assertEqual(status.available, "0.7")
        with self.assertRaisesRegex(ReceiptError, "exceeded its authorization"):
            self.ledger.reserve("next", "0.1")

    def test_repeat_forwarding_or_settlement_refused(self):
        self.ledger.reserve("a", "0.2")
        with self.assertRaisesRegex(ReceiptError, "duplicate"):
            self.ledger.reserve("a", "0.2")
        self.ledger.settle("a", "0.1")
        with self.assertRaises(ReceiptError):
            self.ledger.settle("a", "0.1")
        with self.assertRaises(ReceiptError):
            self.ledger.mark_uncertain("a")

    def test_concurrent_admissions_are_serialized(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._maybe_reserve, n) for n in range(8)]
            admitted = [f.result() for f in futures]
        self.assertEqual(sum(admitted), 1)
        self.assertEqual(self.ledger.snapshot().reserved, "0.8")

    def _maybe_reserve(self, number):
        try:
            BudgetLedger(self.path).reserve(f"r-{number}", "0.8")
            return True
        except ReceiptError:
            return False

    def test_reopens_with_unchanged_limit(self):
        self.ledger.reserve("p", "0.45")
        reopened = BudgetLedger(self.path, budget_usd="1.00")
        self.assertEqual(reopened.snapshot().reserved, "0.45")
        with self.assertRaisesRegex(ReceiptError, "budget differs"):
            BudgetLedger(self.path, budget_usd="2")

    def test_reject_inexact_and_invalid_money(self):
        for value in ("-1", "1e-5", "NaN", "0.0000000000001", "01", 0.1):
            with self.subTest(value=value), self.assertRaises(ReceiptError):
                self.ledger.reserve("bad", value)
        with self.assertRaises(ReceiptError):
            self.ledger.reserve("bad-id", "0")
        with self.assertRaises(ReceiptError):
            self.ledger.reserve("../escape", "0.3")

    def test_private_file_permissions(self):
        if os.name == "posix":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
