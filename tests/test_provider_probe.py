"""Probe credentials only through local fakes; never contact OpenAI."""
import json
import tempfile
import unittest
from pathlib import Path
from cost_to_done.core import ReceiptError
from cost_to_done.provider_probe import probe_models

KEY = "sk-private-test-credential-123456789101112"
MODEL = "gpt-6.1-terra"

class ModelAccessTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.file = Path(d.name) / "private.key"
        self.file.write_text(KEY + "\n", encoding="ascii")
        self.file.chmod(0o600)

    def test_success_without_inference_or_key_disclosure(self):
        output = probe_models(self.file, (MODEL,), transport=lambda model, key: (
            200, json.dumps({"object": "model", "id": model}).encode()))
        self.assertTrue(output["metadata_access_confirmed"])
        self.assertEqual(output["inference_requests"], 0)
        self.assertFalse(output["provider_invoice_reconciled"])
        self.assertNotIn(KEY, json.dumps(output))

    def test_errors_never_expose_key_or_provider_bodies(self):
        for status, expected in ((401, "unauthorized"), (403, "forbidden"),
                                 (404, "model_not_available"), (429, "rate_limited"),
                                 (302, "redirect_refused"), (500, "provider_or_protocol_error")):
            with self.subTest(status=status):
                result = probe_models(self.file, (MODEL,), transport=lambda *_: (
                    status, ("sensitive " + KEY).encode()))
                self.assertEqual(result["models"][0]["access"], expected)
                self.assertNotIn(KEY, json.dumps(result))

    def test_wrong_model_or_malformed_metadata_rejected(self):
        for body in (b'{"object":"model","id":"another"}', b'not-json', b" " * 8193):
            with self.subTest(body=body[:25]):
                result = probe_models(self.file, (MODEL,), transport=lambda *_: (200, body))
                self.assertFalse(result["metadata_access_confirmed"])

    def test_transport_error_redacted(self):
        def fail(*_):
            raise TimeoutError(KEY)
        result = probe_models(self.file, (MODEL,), transport=fail)
        self.assertEqual(result["models"][0]["access"], "transport_error")
        self.assertNotIn(KEY, json.dumps(result))

    def test_invalid_models_and_unsafe_key_never_contact_network(self):
        calls = []
        def fake(*args):
            calls.append(args)
            return (200, b'{}')
        for models in ((), (MODEL, MODEL), ("../bad",), tuple(str(x) for x in range(9))):
            with self.assertRaises(ReceiptError):
                probe_models(self.file, models, transport=fake)
        self.file.chmod(0o644)
        with self.assertRaisesRegex(ReceiptError, "chmod 600"):
            probe_models(self.file, (MODEL,), transport=fake)
        self.assertFalse(calls)

    def test_symlink_key_refused(self):
        link = self.file.parent / "link.key"
        link.symlink_to(self.file)
        with self.assertRaises(ReceiptError):
            probe_models(link, (MODEL,), transport=lambda *_: self.fail())

if __name__ == "__main__":
    unittest.main()
