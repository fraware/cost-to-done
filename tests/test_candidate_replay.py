"""Artifact binding and replay isolation contracts; no model requests."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.replay import captured_candidate, replay_candidate, IMAGE

ROOT = Path(__file__).resolve().parents[1]


class CandidateReplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.job = Path(temp.name).resolve()
        self.artifacts = self.job / "trial" / "artifacts"
        self.artifacts.mkdir(parents=True)
        self.candidate = self.artifacts / "candidate.py"
        self.candidate.write_text("def allocate_cents(total_cents, weights): return []\n")
        self.entry = {"source": "/app/allocate.py", "destination": "artifacts/candidate.py",
                      "type": "file", "status": "ok", "service": None}
        self.manifest = self.artifacts / "manifest.json"
        self.manifest.write_text(json.dumps([self.entry]))

    def test_manifest_binding_and_rejections(self):
        self.assertEqual(captured_candidate(self.job, "allocation-repair"), self.candidate)
        self.entry["status"] = "failed"
        self.manifest.write_text(json.dumps([self.entry]))
        with self.assertRaises(ReceiptError):
            captured_candidate(self.job, "allocation-repair")
        self.entry["status"] = "ok"
        self.manifest.write_text(json.dumps([self.entry]))
        self.candidate.unlink()
        self.candidate.symlink_to(self.manifest)
        with self.assertRaises(ReceiptError):
            captured_candidate(self.job, "allocation-repair")

    def test_fresh_container_has_restricted_inputs(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
            if command[1] == "run":
                self.assertIn(IMAGE, command)
                self.assertIn("none", command)
                self.assertIn("--read-only", command)
                self.assertIn("65534:65534", command)
                self.assertIn("ALL", command)
                self.assertEqual(command.count("--mount"), 2)
                self.assertNotIn(str(ROOT), " ".join(command))
            return subprocess.CompletedProcess(command, 0, stdout=b"")

        with patch("cost_to_done.replay.subprocess.run", side_effect=fake_run), \
             patch.dict("os.environ", {"OPENAI_API_KEY": "not-forwarded"}):
            result = replay_candidate(ROOT, "allocation-repair", self.candidate)
        self.assertEqual(result["outcome"], "pass")
        self.assertTrue(result["cleanup_confirmed"])
        self.assertFalse(result["adversarial_verifier_integrity_established"])
        self.assertEqual([x[1] for x in calls], ["run", "rm", "ps"])

    def test_timeout_and_cleanup_failure_are_unresolved(self):
        def fake_run(command, **kwargs):
            if command[1] == "run":
                raise subprocess.TimeoutExpired(command, 1)
            return subprocess.CompletedProcess(command, 1, stdout=b"")
        with patch("cost_to_done.replay.subprocess.run", side_effect=fake_run):
            result = replay_candidate(ROOT, "allocation-repair", self.candidate)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertFalse(result["independent_process_reexecution"])

    def test_cli_preserves_failed_verdict_and_refuses_overwrite(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from cost_to_done.cli import main
        output = self.job / "replay.json"
        args = ["replay-candidate", "--repo-root", str(ROOT),
                "--task", "allocation-repair", "--candidate", str(self.candidate),
                "--output", str(output)]
        with patch("cost_to_done.replay.replay_candidate", return_value={"outcome": "fail"}) as run, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(args), 1)
            self.assertEqual(json.loads(output.read_text()), {"outcome": "fail"})
            self.assertEqual(main(args), 2)
            self.assertEqual(run.call_count, 1)
