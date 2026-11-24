"""Audit original redacted replay attestations and distinguish failure from completion.

The archive comparison checks byte identity and the recorded verdicts. It does
not execute model-produced code or independently authenticate the original
candidate bytes, which were not published by the historical workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.ledger import _units, _usd
from scripts.audit_development_archive import load_json
from cost_to_done.private_files import publish_private_texts

EXPECTED_MODELS = {"gpt-6.1-terra", "gpt-6.2-sol"}
COMPLETE = "completed_with_unverified_rate_card_estimate"


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def read_archive(path: Path, expected_digest: str) -> dict:
    """Read the sole permitted ZIP member, with bounded size and no extraction."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ReceiptError("unsafe replay archive")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
        raise ReceiptError("replay archive SHA-256 mismatch")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != "replay-attestation.json":
            raise ReceiptError("unexpected replay archive contents")
        member = members[0]
        if (member.is_dir() or stat.S_ISLNK(member.external_attr >> 16)
                or not 0 < member.file_size <= 128_000):
            raise ReceiptError("unsafe replay attestation")
        result = load_json(archive.read(member))
    if not isinstance(result, dict):
        raise ReceiptError("invalid replay attestation")
    return result


def audit(reference_dir: Path, archive_dir: Path, *, starter_sha256: str,
          verifier_sha256: str) -> dict:
    """Validate this exact two-episode cohort; retain costs of failed work."""
    manifest = load_json((reference_dir / "manifest.json").read_bytes())
    observations = manifest["observations"]
    if (manifest.get("schema_version") != 1
            or manifest.get("cohort") != "frontier-allocation-candidate-replay-v1"
            or len(observations) != 2
            or {x["model"] for x in observations} != EXPECTED_MODELS):
        raise ReceiptError("unexpected replay cohort")
    rows = []
    result_hashes = set()
    task_hashes = set()
    replay_script_hashes = set()
    total = 0
    for item in observations:
        model = item["model"]
        if item["file"] != model + ".json" or type(item["artifact_id"]) is not int:
            raise ReceiptError("unsafe replay reference")
        rec = read_archive(archive_dir / (str(item["artifact_id"]) + ".zip"),
                           item["github_reported_zip_sha256"])
        if rec != load_json((reference_dir / item["file"]).read_bytes()):
            raise ReceiptError("replay archive differs from recorded job log")
        replay = rec.get("candidate_replay") or {}
        verdict = rec.get("harbor_trial_outcome")
        if (rec.get("schema_version") != 3 or rec.get("model") != model
                or rec.get("cohort") != manifest["cohort"] or rec.get("task_fixture") != "allocation-repair"
                or rec.get("api") != "responses" or rec.get("reasoning_effort") != "low"
                or rec.get("trial_status") != COMPLETE or rec.get("candidate_capture_requested") is not True
                or rec.get("ledger_observed") is not True or rec.get("gateway_breached") is not False
                or type(rec.get("gateway_pending")) is not int or rec["gateway_pending"] != 0
                or type(rec.get("gateway_uncertain")) is not int or rec["gateway_uncertain"] != 0
                or type(rec.get("gateway_recorded_calls")) is not int or rec["gateway_recorded_calls"] <= 0
                or rec.get("provider_invoice_reconciled") is not False
                or rec.get("provider_spend_limit_verified") is not False
                or rec.get("verifier_independently_reexecuted") is not True
                or rec.get("harbor_replay_agreement") is not True
                or verdict not in ("pass", "fail") or rec.get("replay_status") != verdict
                or replay.get("outcome") != verdict
                or replay.get("task") != "allocation-repair"
                or replay.get("cleanup_confirmed") is not True
                or replay.get("independent_process_reexecution") is not True
                or replay.get("network_mode") != "none"
                or replay.get("provider_credentials_mounted") is not False
                or replay.get("adversarial_verifier_integrity_established") is not False
                or replay.get("verifier_sha256") != verifier_sha256
                or not _digest(replay.get("candidate_sha256"))
                or not _digest(replay.get("replay_script_sha256"))
                or not _digest(rec.get("harbor_task_checksum"))
                or not _digest(rec.get("harbor_raw_result_sha256"))
                or not _digest(rec.get("price_schedule_sha256"))):
            raise ReceiptError("invalid replay identity, outcome, settlement or disclosures")
        result_hashes.add(rec["harbor_raw_result_sha256"])
        task_hashes.add(rec["harbor_task_checksum"])
        replay_script_hashes.add(replay["replay_script_sha256"])
        cost = _units(rec["gateway_rate_card_estimate_usd"])
        total += cost
        rows.append({"model": model, "original_verdict": verdict,
                     "replay_verdict": verdict,
                     "final_source_matches_starter": replay["candidate_sha256"] == starter_sha256,
                     "settled_local_estimate_usd": _usd(cost),
                     "cost_per_completion_usd": _usd(cost) if verdict == "pass" else None})
    if len(result_hashes) != 2 or len(task_hashes) != 1 or len(replay_script_hashes) != 1:
        raise ReceiptError("replay trial identity mismatch")
    return {"schema_version": 1, "status": "original_redacted_replay_archives_verified",
            "workflow_run_id": manifest["workflow_run_id"], "source_commit": manifest["source_commit"],
            "observed": 2, "verifier_agreements": 2,
            "known_rate_card_estimate_usd": _usd(total), "rows": rows,
            "candidate_bytes_publicly_available": False,
            "provider_invoice_reconciled": False, "eligible_for_ranking": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = args.historical_root / "tasks/allocation-repair"
    starter = hashlib.sha256((task / "environment/allocate.py").read_bytes()).hexdigest()
    verifier = hashlib.sha256((task / "tests/test_state.py").read_bytes()).hexdigest()
    report = audit(args.reference_dir, args.archive_dir, starter_sha256=starter, verifier_sha256=verifier)
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    publish_private_texts([(args.output, payload)])
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
