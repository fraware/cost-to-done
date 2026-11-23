"""Regression tests for private, non-overwriting artifact publication."""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cost_to_done.core import ReceiptError
from cost_to_done.private_files import publish_private_texts


class PublicationTests(unittest.TestCase):
    def test_complete_private_payloads_and_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "nested" / "receipt.jsonl"
            second = root / "nested" / "receipt.jsonl.evidence.json"
            publish_private_texts([(second, '{"verified":false}\n'), (first, '{"cost":"0.001"}\n')])
            self.assertEqual(first.read_text(), '{"cost":"0.001"}\n')
            self.assertEqual(second.read_text(), '{"verified":false}\n')
            self.assertEqual(stat.S_IMODE(first.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(second.stat().st_mode), 0o600)
            self.assertEqual(list(first.parent.glob("*.tmp")), [])
            self.assertEqual(list(first.parent.glob(".*.tmp")), [])

    def test_concurrent_destination_creation_fails_closed_and_rolls_back(self):
        """Simulate a competing writer creating the receipt during publication."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sidecar = root / "receipt.evidence.json"
            receipt = root / "receipt.jsonl"
            original_link = os.link

            def competing_link(source: str | os.PathLike[str], destination: str | os.PathLike[str], *args, **kwargs):
                if Path(destination) == receipt:
                    receipt.write_text("competing user's original evidence\n")
                return original_link(source, destination, *args, **kwargs)

            with mock.patch("cost_to_done.private_files.os.link", side_effect=competing_link):
                with self.assertRaisesRegex(ReceiptError, "already exists"):
                    publish_private_texts([(sidecar, "audit record\n"), (receipt, "new receipt\n")])
            self.assertEqual(receipt.read_text(), "competing user's original evidence\n")
            self.assertFalse(sidecar.exists())
            self.assertFalse(any(root.glob(".*.tmp")))

    def test_duplicate_or_symlink_destinations_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "input.jsonl"
            target.write_text("valuable original\n")
            link = root / "receipt.jsonl"
            link.symlink_to(target)
            with self.assertRaisesRegex(ReceiptError, "already exists"):
                publish_private_texts([(link, "bad")])
            self.assertEqual(target.read_text(), "valuable original\n")
            with self.assertRaisesRegex(ReceiptError, "duplicate"):
                publish_private_texts([(root / "same", "a"), (root / "same", "b")])
            self.assertFalse((root / "same").exists())


if __name__ == "__main__":
    unittest.main()
