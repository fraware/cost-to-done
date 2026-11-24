"""Committed snapshot packaging and refusal of unsafe source selections."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.repository_task import prepare_repository_task


class RepositoryTaskTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "fixture")
        (self.repo / "calc.py").write_text("def add(a, b): return a-b\n")
        (self.repo / "test_calc.py").write_text("import unittest\nfrom calc import add\n")
        (self.repo / ".env").write_text("DO_NOT_COPY=fixture")
        (self.repo / "secret.pem").write_text("fixture")
        (self.repo / "link.py").symlink_to("calc.py")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.instruction = self.root / "instruction.md"
        self.instruction.write_text("Repair addition.")
        self.output = self.root / "task"

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def prepare(self, **kwargs):
        options = {"revision": "HEAD", "name": "addition-repair",
                   "sources": ["calc.py"], "tests": ["test_calc.py"],
                   "instruction": self.instruction, "output": self.output}
        options.update(kwargs)
        return prepare_repository_task(self.repo, **options)

    def test_exact_committed_snapshot_and_separate_tests(self):
        (self.repo / "calc.py").write_text("working tree edit\n")
        first = self.prepare()
        self.assertEqual((self.output / "environment/workspace/calc.py").read_text(),
                         "def add(a, b): return a-b\n")
        self.assertFalse((self.output / "environment/workspace/test_calc.py").exists())
        self.assertFalse((self.output / "environment/workspace/.env").exists())
        self.assertTrue((self.output / "tests/test_calc.py").is_file())
        self.assertFalse(first["baseline_qualified"])
        self.assertEqual(first["provider_calls"], 0)
        self.assertEqual(self.prepare(output=self.root / "second"), first)
        with self.assertRaises(ReceiptError):
            self.prepare()

    def test_reject_symlinks_hidden_files_traversal_and_overlap(self):
        for paths in (["link.py"], [".env"], ["secret.pem"], ["../calc.py"],
                      ["missing.py"], ["test_calc.py"], ["calc.py", "calc.py"]):
            with self.subTest(paths=paths), self.assertRaises(ReceiptError):
                self.prepare(sources=paths)
            self.assertFalse(self.output.exists())

    def test_cli(self):
        from cost_to_done.cli import main
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()):
            code = main(["prepare-repo-task", "--repository", str(self.repo),
                         "--name", "addition-repair", "--source", "calc.py",
                         "--test", "test_calc.py", "--instruction", str(self.instruction),
                         "--output", str(self.output)])
        self.assertEqual(code, 0)

    def test_validate_rejects_modified_or_extra_files(self):
        from cost_to_done.repository_task import validate_repository_task
        self.prepare()
        valid = validate_repository_task(self.output)
        self.assertEqual(valid["verified_files"], 6)
        source = self.output / "environment/workspace/calc.py"
        extra = source.parent / "incidental.txt"
        extra.write_text("not in manifest")
        with self.assertRaisesRegex(ReceiptError, "unexpected staged file"):
            validate_repository_task(self.output)
        extra.unlink()
        source.write_text("modified")
        with self.assertRaisesRegex(ReceiptError, "identity mismatch"):
            validate_repository_task(self.output)

    def test_non_root_repository_refused(self):
        subdirectory = self.repo / "subdirectory"
        subdirectory.mkdir()
        with self.assertRaisesRegex(ReceiptError, "root of a local Git"):
            prepare_repository_task(subdirectory, revision="HEAD", name="addition-repair",
                                    sources=["calc.py"], tests=["test_calc.py"],
                                    instruction=self.instruction, output=self.output)

    def test_qualification_binding_and_external_paid_execution_refusal(self):
        import json
        from unittest.mock import patch
        from dataclasses import replace
        from cost_to_done.repository_qualification import qualify_repository_task, check_qualification
        from cost_to_done.live import LiveConfig, plan_live, prepare_task, execute_live
        first = self.prepare()
        (self.repo / "calc.py").write_text("def add(a, b): return a+b\n")
        self.git("add", "calc.py")
        self.git("commit", "-qm", "reference")
        reference = self.root / "reference"
        self.prepare(output=reference)
        def observation(outcome, char):
            return {"complete": True, "observed_trials": 1, "trials": [{
                "agent": "nop", "model": None, "outcome": outcome,
                "task": "cost-to-done/addition-repair", "raw_result_sha256": char*64,
                "task_checksum": char*64}]}
        with patch("cost_to_done.repository_qualification.inspect_harbor_job",
                   side_effect=[observation("fail", "a"), observation("pass", "b")]):
            qual = qualify_repository_task(self.output, reference, self.root / "j1", self.root / "j2")
        path = self.root / "qualification.json"
        path.write_text(json.dumps(qual))
        self.assertEqual(check_qualification(self.output, path, first["task_input_sha256"]), qual)
        with self.assertRaisesRegex(ReceiptError, "pinned task digest"):
            check_qualification(self.output, path, "0"*64)
        runner = Path(__file__).resolve().parents[1]
        cfg = LiveConfig(runner, self.output, self.root / "runs", "test-model-1",
                         runner / "tests/fixtures/mock-price-schedule.json",
                         self.root / "missing-key", "1", api="responses",
                         repository_task_sha256=first["task_input_sha256"],
                         repository_qualification=path)
        self.assertEqual(plan_live(cfg)["repository_execution_scope"], "mock_only")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false", "CTD_REHEARSAL_ONLY": "0"}):
            with self.assertRaisesRegex(ReceiptError, "paid execution is disabled"):
                execute_live(cfg, acknowledged=True)
        self.assertFalse(cfg.jobs_dir.exists())
        staged = self.root / "staged"
        prepare_task(cfg.validated(), staged)
        self.assertIn("COPY workspace/ /app/", (staged / "environment/Dockerfile").read_text())
        self.assertFalse((staged / "ctd-task-manifest.json").exists())
        self.assertEqual((staged / "environment/workspace/calc.py").read_text(),
                         "def add(a, b): return a-b\n")
        self.assertTrue((staged / "tests/test_calc.py").is_file())
        with self.assertRaisesRegex(ReceiptError, "candidate collection"):
            plan_live(replace(cfg, capture_candidate=True))
