"""Execute a single bounded, genuine OpenAI Harbor smoke trial on a trusted runner.

The upstream credential is supplied by the trusted operator or GitHub Actions
secret environment. It is copied to a private temporary file, is exposed only
to the gateway container through the existing read-only Compose secret mount,
and is never forwarded to the agent. Public artifacts are a minimal redacted
attestation; raw driver logs and trial transcripts are deliberately excluded.

This trial does NOT prove a hard provider-side spend limit or invoice amount.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.private_files import publish_private_texts


def attestation(outcome: dict, model: str) -> dict:
    """Build an evidence report containing no prompts, credentials, or transcripts."""
    trial = outcome.get("trial") or {}
    ledger = outcome.get("gateway_snapshot") or {}
    entries = outcome.get("gateway_entries") or []
    status = outcome.get("status", "unknown")
    if status not in (
        "incomplete_or_uncertain", "requires_financial_reconciliation",
        "no_metered_requests", "completed_with_unverified_rate_card_estimate",
    ):
        status = "unknown"
    return {
        "schema_version": 1,
        "evidence_kind": "single_real_provider_smoke_local_observation",
        "model": model,
        "trial_status": status,
        "harbor_trial_outcome": trial.get("outcome"),
        "harbor_task_checksum": trial.get("task_checksum"),
        "harbor_raw_result_sha256": trial.get("raw_result_sha256"),
        "harbor_reported_elapsed_seconds": trial.get("elapsed_seconds"),
        "gateway_recorded_calls": len(entries),
        "gateway_rate_card_estimate_usd": ledger.get("settled"),
        "gateway_pending": ledger.get("pending"),
        "gateway_uncertain": ledger.get("uncertain"),
        "gateway_breached": ledger.get("breached"),
        "price_schedule_sha256": outcome.get("price_schedule_sha256"),
        "provider_invoice_reconciled": False,
        "provider_spend_limit_verified": False,
        "verifier_independently_reexecuted": False,
        "publication_scope": "redacted_status_and_hashes_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--attestation-dir", required=True, type=Path)
    parser.add_argument("--budget-usd", default="1")
    parser.add_argument("--max-wall-seconds", type=int, default=900)
    args = parser.parse_args()

    output = args.attestation_dir / "attestation.json"
    base = {
        "schema_version": 1,
        "evidence_kind": "single_real_provider_smoke_local_observation",
        "model": args.model, "trial_status": "credential_unavailable",
        "provider_invoice_reconciled": False, "provider_spend_limit_verified": False,
    }
    # The credential is injected exclusively into this trusted workflow step.
    # Child Harbor/Compose processes receive a separately constructed allowlist.
    credential = os.environ.pop("CTD_OPENAI_SECRET", "")
    if not credential:
        publish_private_texts([(output, json.dumps(base, sort_keys=True, indent=2) + "\n")])
        print(json.dumps({"model": args.model, "status": "credential_unavailable"}))
        return 2

    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as directory:
        key_path = Path(directory) / "upstream.key"
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(credential)
        del credential
        config = LiveConfig(
            repo_root=args.repo_root,
            task=args.repo_root / "tasks/allocation-repair",
            jobs_dir=args.repo_root / "runs" / "real-provider-smoke",
            model=args.model,
            price_schedule=args.prices,
            key_file=key_path,
            budget_usd=args.budget_usd,
            job_name=args.job_name,
            max_turns=5,
            max_wall_seconds=args.max_wall_seconds,
        )
        # Explicit operator authorization for one real trial was supplied.
        # This acknowledgement is NOT evidence of a provider-side hard limit.
        outcome = execute_live(config, acknowledged=True)

    record = attestation(outcome, args.model)
    args.attestation_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    publish_private_texts([(output, json.dumps(record, sort_keys=True, indent=2) + "\n")])
    print(json.dumps({
        "model": args.model, "status": record["trial_status"],
        "verifier": record.get("harbor_trial_outcome"),
        "inference_requests": record.get("gateway_recorded_calls"),
        "rate_card_estimate_usd": record.get("gateway_rate_card_estimate_usd"),
        "billing_verified": False, "provider_spend_limit_verified": False,
    }, sort_keys=True))
    return 0 if record["trial_status"] == "completed_with_unverified_rate_card_estimate" else 2


if __name__ == "__main__":
    raise SystemExit(main())
