"""CI-only live-runner rehearsal guards and offline command contract."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_live_rehearsal import FAKE_KEY, run


class LiveRehearsalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.key = self.base / "fake-key"
        self.key.write_text(FAKE_KEY + "\n", encoding="ascii")
        self.key.chmod(0o600)
        self.repo = Path(__file__).resolve().parents[1]
        self.out = self.base / "runs"

    def test_refuses_execution_outside_ci(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "false", "CTD_REHEARSAL_ONLY": "1"}):
            with self.assertRaisesRegex(RuntimeError, "CI-only"):
                run(self.repo, self.out, self.key)

    def test_refuses_unknown_provider_credential(self) -> None:
        self.key.write_text("some-private-credential\n", encoding="ascii")
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "CTD_REHEARSAL_ONLY": "1"}):
            with self.assertRaisesRegex(RuntimeError, "fictional credential"):
                run(self.repo, self.out, self.key)

    def test_refuses_output_overwrite(self) -> None:
        self.out.mkdir()
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "CTD_REHEARSAL_ONLY": "1"}):
            with self.assertRaisesRegex(RuntimeError, "already exists"):
                run(self.repo, self.out, self.key)

    def test_preserves_live_command_with_one_additional_mock_overlay(self) -> None:
        from cost_to_done.live import LiveConfig, HARBOR_VERSION
        self.assertEqual(HARBOR_VERSION, "0.27.0")
        original = LiveConfig.command

        def observe(config: LiveConfig, *, acknowledged: bool = False) -> dict:
            self.assertTrue(acknowledged)
            cmd = config.command(task_copy=Path("/fixture/task"), token="test-token")
            self.assertEqual(cmd.count("--extra-docker-compose"), 2)
            self.assertEqual(cmd[-2:], [
                "--extra-docker-compose", str(self.repo / "tests/live/compose-rehearsal.yaml"),
            ])
            self.assertIn("max_output_tokens=4096", cmd)
            self.assertNotIn(FAKE_KEY, " ".join(cmd))
            return {
                "status": "completed_with_unverified_rate_card_estimate",
                "trial": {"outcome": "pass"},
                "gateway_snapshot": {"settled": "0.0236"},
                "provider_invoice_reconciled": False,
            }

        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "CTD_REHEARSAL_ONLY": "1"}), \
                mock.patch("scripts.run_live_rehearsal.execute_live", side_effect=observe):
            outcome = run(self.repo, self.out, self.key)
        self.assertIs(LiveConfig.command, original)
        self.assertEqual(outcome["status"], "mock-live-rehearsal-complete")
        self.assertTrue(outcome["mock_only"])
        self.assertFalse(outcome["provider_invoice_reconciled"])

    def test_missing_evidence_is_rejected(self) -> None:
        from scripts.check_live_rehearsal import check
        with self.assertRaises(FileNotFoundError):
            check(self.out)


if __name__ == "__main__":
    unittest.main()
