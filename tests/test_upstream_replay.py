"""Unit tests for upstream capture binding; actual Docker replay is in CI."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.replay import captured_source, replay_source
from cost_to_done.upstream_replay import capture_declaration, replay_upstream, MODULES
from cost_to_done.upstream_pilot import STARTERS


class UpstreamReplayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.task = next(iter(STARTERS))
        self.module = MODULES[self.task]

    def test_capture_declaration_exact_and_unique(self):
        path = self.root / "task.toml"
        path.write_text("[task]\nname='example'\n")
        capture_declaration(self.root, self.task)
        self.assertIn(f'source = "/app/{self.module}"', path.read_text())
        with self.assertRaises(ReceiptError):
            capture_declaration(self.root, self.task)
        with self.assertRaises(ReceiptError):
            capture_declaration(self.root, "unapproved")

    def collection(self):
        job = self.root / "job"
        artifacts = job / "trial" / "artifacts"
        artifacts.mkdir(parents=True)
        result = artifacts.parent / "result.json"
        result.write_bytes(b'{"test":"synthetic"}')
        candidate = artifacts / "candidate.py"
        candidate.write_bytes(b"def test(): return True\n")
        manifest = [{"destination": "artifacts/candidate.py", "source": "/app/" + self.module,
                     "type": "file", "status": "ok", "service": "main"}]
        (artifacts / "manifest.json").write_text(json.dumps(manifest))
        return job, candidate, hashlib.sha256(result.read_bytes()).hexdigest()

    def test_capture_binds_trial_and_source(self):
        job, candidate, raw = self.collection()
        self.assertEqual(captured_source(job, "/app/" + self.module,
                                        expected_result_sha256=raw), candidate)
        with self.assertRaises(ReceiptError):
            captured_source(job, "/app/other.py", expected_result_sha256=raw)
        with self.assertRaises(ReceiptError):
            captured_source(job, "/app/" + self.module, expected_result_sha256="0"*64)

    def test_replay_uses_pristine_verifier(self):
        job, candidate, raw = self.collection()
        starter = self.root / "starter"
        tests = starter / "tests"
        tests.mkdir(parents=True)
        verifier = tests / "test_regression.py"
        verifier.write_bytes(b"import unittest\n")
        manifest = {"task": self.task, "task_input_sha256": STARTERS[self.task],
                    "files": {"tests/test_regression.py": {
                        "sha256": hashlib.sha256(verifier.read_bytes()).hexdigest()}}}
        with patch("cost_to_done.upstream_replay.validate_upstream_starter", return_value=manifest), \
                patch("cost_to_done.upstream_replay.replay_source",
                      return_value={"outcome": "pass"}) as run:
            result = replay_upstream(starter, job, raw)
            self.assertEqual(result["harbor_raw_result_sha256"], raw)
            self.assertEqual(result["base_task_input_sha256"], STARTERS[self.task])
            run.assert_called_once_with(self.task, self.module, candidate.read_bytes(),
                                        "test_regression.py", verifier.read_bytes(), timeout=45)
            verifier.write_bytes(b"changed")
            with self.assertRaises(ReceiptError):
                replay_upstream(starter, job, raw)

    def test_replay_rejects_escaped_paths_before_docker(self):
        for name in ("../module.py", "/tmp/module.py", "Lib/../module.py"):
            with self.assertRaises(ReceiptError):
                replay_source(self.task, name, b"x", "test_regression.py", b"x")
        with self.assertRaises(ReceiptError):
            replay_source(self.task, self.module, b"x", "../test_regression.py", b"x")
