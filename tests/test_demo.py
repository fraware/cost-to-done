"""The installed demo is deterministic, explicitly synthetic, and no-clobber."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from cost_to_done.cli import main
from cost_to_done.core import parse_trial
from cost_to_done.demo import demo_rows


class DemoTests(unittest.TestCase):
    def test_fixture(self):
        rows = demo_rows()
        self.assertEqual(rows, demo_rows())
        self.assertEqual(len(rows), 90)
        self.assertEqual(len({row["trial_id"] for row in rows}), 90)
        for row in rows:
            parse_trial(row)

    def test_demo_cli_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo.html"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["demo", "--output", str(target)]), 0)
                first = target.read_bytes()
                self.assertIn(b"synthetic", first.lower())
                self.assertEqual(main(["demo", "--output", str(target)]), 2)
                self.assertEqual(target.read_bytes(), first)
