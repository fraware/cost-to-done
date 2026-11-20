"""CLI behavior for the local inference gateway; no network/API access."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from cost_to_done.cli import main


class GatewayCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.price = self.root / "price.json"
        self.price.write_text(json.dumps({
            "model": "test-model-1", "effective_date": "2026-11-20",
            "source_url": "https://example.com/pricing", "input_per_million_usd": "1",
            "output_per_million_usd": "5"
        }), encoding="utf-8")
        self.ledger = self.root / "new-ledger.sqlite3"

    def call(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_plan_does_not_create_ledger_or_require_credentials(self):
        code, out, err = self.call("gateway-serve", "--price-schedule", str(self.price),
                                   "--ledger", str(self.ledger), "--budget-usd", "0.5")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["status"], "plan_only")
        self.assertFalse(self.ledger.exists())

    def test_live_mode_refuses_unacknowledged_provider_exposure(self):
        code, out, err = self.call("gateway-serve", "--price-schedule", str(self.price),
                                   "--ledger", str(self.ledger), "--budget-usd", "0.5", "--serve")
        self.assertEqual(code, 2)
        self.assertIn("acknowledge-no-provider-hard-cap", err)
        self.assertFalse(self.ledger.exists())

    def test_invalid_decimal_rejected_before_ledger_creation(self):
        code, out, err = self.call("gateway-serve", "--price-schedule", str(self.price),
                                   "--ledger", str(self.ledger), "--budget-usd", "NaN")
        self.assertEqual(code, 2)
        self.assertFalse(self.ledger.exists())

    def test_ledger_status_rejects_uninitialized_file(self):
        code, out, err = self.call("gateway-status", str(self.ledger))
        self.assertEqual(code, 2)
        self.assertIn("ledger needs", err)


if __name__ == "__main__":
    unittest.main()
