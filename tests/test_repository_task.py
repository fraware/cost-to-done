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
