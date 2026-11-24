"""Five negative controls for saved real-model single-task evidence."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.check_real_smoke_evidence import EvidenceError, FOLDER, validate

REPO = Path(__file__).resolve().parents[1]

class RealPilotEvidenceTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        (self.root / FOLDER).parent.mkdir(parents=True)
        shutil.copytree(REPO / FOLDER, self.root / FOLDER)
        prices = self.root / "experiments/live"
        prices.mkdir(parents=True)
        for file in (REPO / "experiments/live").glob("prices-gpt-5.4*.json"):
            shutil.copy2(file,prices/file.name)

    def test_exact_source_records_are_valid_but_unranked(self):
        report = validate(self.root)
        self.assertFalse(report["eligible_for_ranking"])
        self.assertFalse(report["provider_invoice_reconciled"])
        self.assertEqual([row["gateway_calls"] for row in report["observations"]],[3,5])
        self.assertEqual([row["rate_card_estimate_usd"] for row in report["observations"]],["0.021935","0.010698"])

    def test_source_record_modification_detected(self):
        path = self.root / FOLDER / "gpt-5.4-2026-03-05.json"
        path.write_text(path.read_text().replace("0.021935","0.001"))
        with self.assertRaisesRegex(EvidenceError, "SHA-256 mismatch"):
            validate(self.root)

    def test_false_invoice_claim_rejected_even_with_new_digest(self):
        path = self.root / FOLDER / "gpt-5.4-mini-2026-03-17.json"
        obj = json.loads(path.read_text())
        obj["provider_invoice_reconciled"] = True
        data = (json.dumps(obj,sort_keys=True,indent=2)+"\n").encode()
        path.write_bytes(data)
        manifest_path = self.root / FOLDER / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][1]["sha256"] = hashlib.sha256(data).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(EvidenceError, "unsupported invoice"):
            validate(self.root)

    def test_changed_price_schedule_rejected(self):
        path=self.root/"experiments/live/prices-gpt-5.4-2026-03-05.json"
        data=json.loads(path.read_text())
        data["input_per_million_usd"]="1000"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(EvidenceError,"price schedule identity mismatch"):
            validate(self.root)

    def test_unsafe_file_path_rejected(self):
        path=self.root/FOLDER/"manifest.json"
        data=json.loads(path.read_text())
        data["artifacts"][0]["path"]="../secret.json"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(EvidenceError,"unsafe artifact path"):
            validate(self.root)
