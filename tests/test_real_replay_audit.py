"""Exercise archival accounting with redacted historical observations."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from scripts.audit_real_replay import audit

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "evidence/2026-11-24-real-candidate-replay"


class RealReplayAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.ref = self.root / "reference"
        shutil.copytree(REFERENCE, self.ref)
        self.manifest = json.loads((self.ref / "manifest.json").read_text())
        task = ROOT / "tasks/allocation-repair"
        self.starter = hashlib.sha256((task / "environment/allocate.py").read_bytes()).hexdigest()
        self.verifier = hashlib.sha256((task / "tests/test_state.py").read_bytes()).hexdigest()
        self.write_archives()

    def write_archives(self):
        # Local test ZIPs are synthetic containers for the transcribed records,
        # not the original Actions archives. The workflow checks original bytes.
        for item in self.manifest["observations"]:
            path = self.root / (str(item["artifact_id"]) + ".zip")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("replay-attestation.json", (self.ref / item["file"]).read_bytes())
            item["github_reported_zip_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.ref / "manifest.json").write_text(json.dumps(self.manifest))

    def run_audit(self):
        return audit(self.ref, self.root, starter_sha256=self.starter,
                     verifier_sha256=self.verifier)

    def test_failure_cost_retained_and_ratio_undefined(self):
        result = self.run_audit()
        rows = {r["model"]: r for r in result["rows"]}
        self.assertEqual(result["known_rate_card_estimate_usd"], "0.023178")
        self.assertEqual(result["verifier_agreements"], 2)
        terra = rows["gpt-6.1-terra"]
        self.assertEqual(terra["settled_local_estimate_usd"], "0.003234")
        self.assertIsNone(terra["cost_per_completion_usd"])
        self.assertTrue(terra["final_source_matches_starter"])
        self.assertEqual(rows["gpt-6.2-sol"]["cost_per_completion_usd"], "0.019944")
        self.assertFalse(result["eligible_for_ranking"])

    def test_archive_tampering_and_record_disagreement(self):
        item = self.manifest["observations"][0]
        path = self.root / (str(item["artifact_id"]) + ".zip")
        with path.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ReceiptError, "SHA-256"):
            self.run_audit()
        self.write_archives()
        rec_path = self.ref / item["file"]
        rec = json.loads(rec_path.read_text())
        rec["gateway_rate_card_estimate_usd"] = "0"
        rec_path.write_text(json.dumps(rec))
        with self.assertRaisesRegex(ReceiptError, "differs"):
            self.run_audit()

    def test_rehashed_financial_or_verifier_claim_rejected(self):
        item = self.manifest["observations"][0]
        path = self.ref / item["file"]
        rec = json.loads(path.read_text())
        rec["gateway_uncertain"] = 1
        path.write_text(json.dumps(rec))
        self.write_archives()
        with self.assertRaisesRegex(ReceiptError, "settlement"):
            self.run_audit()
