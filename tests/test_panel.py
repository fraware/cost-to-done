"""The prospective panel is deterministic, matched and credential-free."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from cost_to_done.cli import main
from cost_to_done.core import ReceiptError
from cost_to_done.panel import build_panel

ROOT = Path(__file__).resolve().parents[1]


class PanelTests(unittest.TestCase):
    def test_default_plan_is_deterministic_and_matched(self):
        plan = build_panel(ROOT)
        self.assertEqual(plan, build_panel(ROOT))
        self.assertEqual(plan["planned_trial_count"], 6)
        self.assertEqual(plan["estimated_admission_total_usd"], "6")
        self.assertFalse(plan["paid_execution_authorized"])
        self.assertFalse(plan["provider_hard_cap_verified"])
        self.assertEqual(len({trial["trial_id"] for trial in plan["trials"]}), 6)
        self.assertEqual(set(Counter((x["task"], x["configuration"]) for x in plan["trials"]).values()), {1})
        for left, right in zip(plan["trials"][::2], plan["trials"][1::2]):
            self.assertEqual((left["task"], left["repetition"]), (right["task"], right["repetition"]))
            self.assertNotEqual(left["configuration"], right["configuration"])
        firsts = Counter(x["configuration"] for x in plan["trials"][::2])
        self.assertLessEqual(max(firsts.values()) - min(firsts.values()), 1)
        self.assertEqual(len(plan["plan_sha256"]), 64)

    def test_ceiling_is_exact_and_fails_closed(self):
        with self.assertRaisesRegex(ReceiptError, "ceiling"):
            build_panel(ROOT, repetitions=3)
        plan = build_panel(ROOT, repetitions=3, budget_per_trial="0.25", max_total_usd="4.5")
        self.assertEqual(plan["planned_trial_count"], 18)
        self.assertEqual(plan["estimated_admission_total_usd"], "4.5")
        self.assertEqual(set(Counter((x["task"], x["configuration"]) for x in plan["trials"]).values()), {3})
        for bad in (0, 11, True):
            with self.assertRaises(ReceiptError):
                build_panel(ROOT, repetitions=bad)

    def test_cli_private_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "panel.json"
            args = ["plan-panel", "--repo-root", str(ROOT), "--output", str(output)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 0)
                before = output.read_bytes()
                self.assertEqual(json.loads(before)["status"], "plan_only")
                self.assertEqual(main(args), 2)
                self.assertEqual(output.read_bytes(), before)
