"""Offline contract checks against the inspected Harbor result schema v1."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError, analyze, parse_trial
from cost_to_done.harbor import import_harbor, write_harbor_receipts

DIGEST = "a" * 64
VERIFIER = "b" * 64


def harbor_result(*, model="model", cost=0.2, reward=1, checksum="pin-1", trial_id="uuid-1"):
    return {
        "schema_version": 1,
        "id": trial_id,
        "task_name": "repair-1",
        "task_checksum": checksum,
        "agent_info": {"name": "pi", "version": "1", "model_info": {"provider": "provider", "name": model}},
        "agent_result": {"n_input_tokens": 10, "cost_usd": cost},
        "verifier_result": {"rewards": {"reward": reward}},
        "started_at": "2026-11-20T00:00:00+00:00",
        "finished_at": "2026-11-20T00:00:12+00:00",
        "exception_info": None,
    }


class ImportHarborTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.trial_dir = self.root / "job-a" / "trials" / "repair-1__pi__1"
        self.trial_dir.mkdir(parents=True)
        self.result = harbor_result()
        self.manifest = {
            "schema_version": 1,
            "tasks": {"repair-1": {
                "task_digest": DIGEST,
                "verifier_digest": VERIFIER,
                "harbor_task_checksum": "pin-1",
            }},
            "jobs": [{
                "path": "job-a",
                "configuration_id": "pi+provider/model",
                "agent": "pi",
                "model": "provider/model",
                "harness_digest": DIGEST,
                "retry_policy": "independent-trials",
                "n_attempts": 1,
                "expected_tasks": ["repair-1"],
                "agent_version": "1",
            }],
        }
        self.save()

    def save(self):
        (self.trial_dir / "result.json").write_text(json.dumps(self.result))
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))

    def test_successful_import_and_report(self):
        receipt = import_harbor(self.root / "manifest.json")[0]
        self.assertEqual(receipt["attempts"][0]["cost_source"], "rate_card_estimate")
        self.assertEqual(receipt["attempts"][0]["seconds"], 12.0)
        self.assertEqual(analyze([parse_trial(receipt)])["rows"][0]["total_cost_usd"], "0.200000000000")
        target = self.root / "new" / "receipts.jsonl"
        self.assertEqual(write_harbor_receipts(self.root / "manifest.json", target), 1)
        self.assertEqual(len(target.read_text().splitlines()), 1)
        with self.assertRaisesRegex(ReceiptError, "already exists"):
            write_harbor_receipts(self.root / "manifest.json", target)

    def test_missing_cost_never_counts_as_zero(self):
        self.result["agent_result"].pop("cost_usd")
        self.save()
        with self.assertRaisesRegex(ReceiptError, "missing"):
            import_harbor(self.root / "manifest.json")

    def test_wrong_model_rejected(self):
        self.result["agent_info"]["model_info"]["name"] = "different"
        self.save()
        with self.assertRaisesRegex(ReceiptError, "mismatch"):
            import_harbor(self.root / "manifest.json")

    def test_wrong_checksum_rejected(self):
        self.result["task_checksum"] = "different"
        self.save()
        with self.assertRaisesRegex(ReceiptError, "checksum differs"):
            import_harbor(self.root / "manifest.json")

    def test_partially_correct_is_failure(self):
        self.result["verifier_result"]["rewards"]["reward"] = 0.5
        self.save()
        self.assertEqual(import_harbor(self.root / "manifest.json")[0]["attempts"][0]["outcome"], "fail")

    def test_infrastructure_error_not_credited(self):
        self.result["exception_info"] = {"exception_type": "Timeout"}
        self.save()
        self.assertEqual(import_harbor(self.root / "manifest.json")[0]["attempts"][0]["outcome"], "infrastructure_error")

    def test_missing_verifier_infra_not_pass(self):
        self.result["verifier_result"] = None
        self.save()
        self.assertEqual(import_harbor(self.root / "manifest.json")[0]["attempts"][0]["outcome"], "infrastructure_error")

    def test_no_partial_outputs_on_failure(self):
        self.result["agent_result"]["cost_usd"] = -2
        self.save()
        target = self.root / "receipts.jsonl"
        with self.assertRaises(ReceiptError):
            write_harbor_receipts(self.root / "manifest.json", target)
        self.assertFalse(target.exists())

    def test_multi_step_cost_is_sum(self):
        self.result.pop("agent_result")
        self.result["step_results"] = [
            {"agent_result": {"cost_usd": 0.1}, "exception_info": None},
            {"agent_result": {"cost_usd": 0.2}, "exception_info": None},
        ]
        self.save()
        self.assertEqual(import_harbor(self.root / "manifest.json")[0]["attempts"][0]["cost_usd"], "0.300000000000")


    def test_harbor_026_direct_trial_layout_supported(self):
        self.save()
        self.trial_dir.joinpath("result.json").unlink()
        modern = self.root / "job-a" / "allocation-repair__abc"
        modern.mkdir()
        (modern / "result.json").write_text(json.dumps(self.result))
        self.assertEqual(len(import_harbor(self.root / "manifest.json")), 1)

    def test_path_traversal_rejected(self):
        self.manifest["jobs"][0]["path"] = "../outside"
        self.save()
        with self.assertRaisesRegex(ReceiptError, "relative child directory"):
            import_harbor(self.root / "manifest.json")

    def test_absolute_path_rejected(self):
        self.manifest["jobs"][0]["path"] = str(self.trial_dir.parent.parent)
        self.save()
        with self.assertRaisesRegex(ReceiptError, "relative child directory"):
            import_harbor(self.root / "manifest.json")

    def test_incomplete_task_roster_rejected(self):
        self.manifest["jobs"][0]["expected_tasks"] = ["repair-1", "repair-2"]
        self.save()
        with self.assertRaisesRegex(ReceiptError, "incomplete job"):
            import_harbor(self.root / "manifest.json")

    def test_agent_version_mismatch_rejected(self):
        self.manifest["jobs"][0]["agent_version"] = "different"
        self.save()
        with self.assertRaisesRegex(ReceiptError, "agent version mismatch"):
            import_harbor(self.root / "manifest.json")

    def test_unsupported_harbor_schema_rejected(self):
        self.result["schema_version"] = 9
        self.save()
        with self.assertRaisesRegex(ReceiptError, "schema_version"):
            import_harbor(self.root / "manifest.json")

    def test_duplicate_task_in_single_job_rejected(self):
        second = self.trial_dir.parent / "second"
        second.mkdir()
        (second / "result.json").write_text(json.dumps({**self.result, "id": "another"}))
        self.manifest["jobs"][0].pop("expected_tasks")
        self.save()
        with self.assertRaisesRegex(ReceiptError, "duplicate task"):
            import_harbor(self.root / "manifest.json")

    def test_manifest_retry_policy_must_be_independent(self):
        self.manifest["jobs"][0]["n_attempts"] = 3
        self.save()
        with self.assertRaisesRegex(ReceiptError, "one Harbor attempt"):
            import_harbor(self.root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
