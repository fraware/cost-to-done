"""Artifact binding and replay isolation contracts; no model requests."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.replay import captured_candidate, replay_candidate, IMAGE, TEST_FAILURE_EXIT, REPLAY_SCRIPT

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
                self.assertEqual(command[command.index("--log-driver") + 1], "none")
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

    def test_only_completed_test_verdicts_are_classified(self):
        for code, verdict in ((0, "pass"), (TEST_FAILURE_EXIT, "fail"),
                              (1, "unresolved"), (2, "unresolved"),
                              (125, "unresolved"), (126, "unresolved"),
                              (127, "unresolved"), (137, "unresolved")):
            def fake_run(command, **kwargs):
                return subprocess.CompletedProcess(
                    command, code if command[1] == "run" else 0, stdout=b"")
            with self.subTest(code=code), patch("cost_to_done.replay.subprocess.run", side_effect=fake_run):
                result = replay_candidate(ROOT, "allocation-repair", self.candidate)
                self.assertEqual(result["outcome"], verdict)
                self.assertEqual(result["independent_process_reexecution"], verdict != "unresolved")
                self.assertTrue(result["cleanup_confirmed"])
        self.assertIn(f"else {TEST_FAILURE_EXIT}", REPLAY_SCRIPT)

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

    def test_artifact_is_bound_to_exact_result(self):
        import hashlib
        result = self.artifacts.parent / "result.json"
        result.write_text('{"example":true}')
        digest = hashlib.sha256(result.read_bytes()).hexdigest()
        self.assertEqual(captured_candidate(self.job, "allocation-repair",
                                           expected_result_sha256=digest), self.candidate)
        with self.assertRaises(ReceiptError):
            captured_candidate(self.job, "allocation-repair", expected_result_sha256="a"*64)

    def test_replay_does_not_erase_cost_or_claim_agreement(self):
        from scripts.run_real_candidate_replay import replay_record
        outcome = {"api": "responses", "reasoning_effort": "low",
                   "candidate_capture_requested": True, "private_job_dir": str(self.job),
                   "status": "completed_with_unverified_rate_card_estimate",
                   "trial": {"outcome": "pass", "raw_result_sha256": "a"*64},
                   "gateway_snapshot": {"settled": "0.02"}, "gateway_entries": [{}]}
        with patch("scripts.run_real_candidate_replay.captured_candidate", return_value=self.candidate), \
             patch("scripts.run_real_candidate_replay.replay_candidate", return_value={
                 "outcome": "fail", "independent_process_reexecution": True}):
            record = replay_record(ROOT, outcome, "gpt-6.1-terra")
        self.assertEqual(record["gateway_rate_card_estimate_usd"], "0.02")
        self.assertTrue(record["verifier_independently_reexecuted"])
        self.assertFalse(record["harbor_replay_agreement"])
