"""Real-provider smoke attestation tests. No paid network requests."""
import unittest
from scripts.run_real_model_smoke import attestation

class SmokeAttestationTests(unittest.TestCase):
    def test_success_retains_verifier_and_estimated_spend_with_disclosures(self):
        result = attestation({
            "status": "completed_with_unverified_rate_card_estimate",
            "trial": {"outcome": "pass", "task_checksum": "a" * 64,
                      "raw_result_sha256": "b" * 64, "elapsed_seconds": 38.2},
            "gateway_snapshot": {"settled": "0.034", "pending": 0,
                                 "uncertain": 0, "breached": False},
            "gateway_entries": [{"request_id": "one"}, {"request_id": "two"}],
            "price_schedule_sha256": "c" * 64,
        }, "gpt-6.1-terra")
        self.assertEqual(result["gateway_recorded_calls"], 2)
        self.assertEqual(result["harbor_trial_outcome"], "pass")
        self.assertEqual(result["gateway_rate_card_estimate_usd"], "0.034")
        self.assertFalse(result["provider_invoice_reconciled"])
        self.assertFalse(result["provider_spend_limit_verified"])

    def test_incomplete_does_not_invent_cost_or_success(self):
        result = attestation({"status": "incomplete_or_uncertain"}, "gpt-6.2-sol")
        self.assertIsNone(result["harbor_trial_outcome"])
        self.assertIsNone(result["gateway_rate_card_estimate_usd"])
        self.assertEqual(result["gateway_recorded_calls"], 0)
        self.assertFalse(result["verifier_independently_reexecuted"])

    def test_native_attestation_preserves_protocol_and_unknown_calls(self):
        result = attestation({"api": "responses", "reasoning_effort": "low",
                              "status": "incomplete_or_uncertain"}, "gpt-6.2-sol")
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["api"], "responses")
        self.assertEqual(result["reasoning_effort"], "low")
        self.assertFalse(result["ledger_observed"])
        self.assertIsNone(result["gateway_recorded_calls"])

    def test_arbitrary_internal_status_is_not_publicly_trusted(self):
        result = attestation({"status": "secret", "trial": {"outcome": "pass"}}, "gpt-6.1-terra")
        self.assertEqual(result["trial_status"], "unknown")
        self.assertNotIn("secret", str(result))
