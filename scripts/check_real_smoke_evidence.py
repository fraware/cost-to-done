"""Check recorded first real-model pilot evidence; NEVER create model rankings.

This is internal consistency and source-hash validation, not a cryptographic
attestation of actual execution, an invoice audit, or a verifier replay.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

FOLDER = Path("evidence/2026-11-24-first-openai-harbor")
ALLOWED = {"gpt-5.4-2026-03-05", "gpt-5.4-mini-2026-03-17"}
EXPECTED_KEYS = {
    "evidence_kind", "gateway_breached", "gateway_pending",
    "gateway_rate_card_estimate_usd", "gateway_recorded_calls", "gateway_uncertain",
    "harbor_raw_result_sha256", "harbor_reported_elapsed_seconds",
    "harbor_task_checksum", "harbor_trial_outcome", "model",
    "price_schedule_sha256", "provider_invoice_reconciled",
    "provider_spend_limit_verified", "publication_scope", "schema_version",
    "trial_status", "verifier_independently_reexecuted",
}

class EvidenceError(ValueError):
    """A saved pilot artifact violates a declared integrity or scope contract."""

def _read(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise EvidenceError("missing or unsafe evidence file")
    raw = path.read_bytes()
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("invalid evidence JSON") from exc
    if not isinstance(data, dict):
        raise EvidenceError("evidence must be JSON object")
    return data, raw

def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

def validate(root: Path):
    """Return only pinned, unranked observations after checking all source files."""
    root = Path(root).resolve(strict=True)
    manifest, _ = _read(root / FOLDER / "manifest.json")
    if manifest.get("schema_version") != 1 or manifest.get("evidence_kind") != "first_real_openai_harbor_single_task_smoke":
        raise EvidenceError("invalid source manifest")
    if not isinstance(manifest.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]):
        raise EvidenceError("invalid source Git commit")
    if manifest.get("source_run") != "https://github.com/fraware/cost-to-done/actions/runs/45309990728":
        raise EvidenceError("source run mismatch")
    descriptors = manifest.get("artifacts")
    if not isinstance(descriptors, list) or len(descriptors) != 2:
        raise EvidenceError("expected exactly two records")
    seen, tasks, observations = set(), set(), []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise EvidenceError("invalid artifact descriptor")
        filename = descriptor.get("path")
        if not isinstance(filename, str) or filename != Path(filename).name or not filename.endswith(".json"):
            raise EvidenceError("unsafe artifact path")
        record, raw = _read(root / FOLDER / filename)
        if not _digest(descriptor.get("sha256")) or hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
            raise EvidenceError("attestation SHA-256 mismatch")
        if not _digest(descriptor.get("workflow_artifact_zip_sha256")) or type(descriptor.get("workflow_artifact_id")) is not int or descriptor["workflow_artifact_id"] <= 0:
            raise EvidenceError("invalid workflow artifact metadata")
        if set(record) != EXPECTED_KEYS or record.get("schema_version") != 1:
            raise EvidenceError("unrecognized attestation schema")
        model = record.get("model")
        if model not in ALLOWED or model in seen or filename != model + ".json":
            raise EvidenceError("unexpected or repeated model")
        seen.add(model)
        price, _ = _read(root / "experiments/live" / f"prices-{model}.json")
        if price.get("model") != model or set(price) != {"model","effective_date","source_url","input_per_million_usd","output_per_million_usd"}:
            raise EvidenceError("model price card mismatch")
        digest = hashlib.sha256(json.dumps(price, sort_keys=True, separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        if record["price_schedule_sha256"] != digest:
            raise EvidenceError("price schedule identity mismatch")
        if not _digest(record["harbor_task_checksum"]) or not _digest(record["harbor_raw_result_sha256"]):
            raise EvidenceError("invalid Harbor hashes")
        tasks.add(record["harbor_task_checksum"])
        if record["harbor_trial_outcome"] != "pass" or record["trial_status"] != "completed_with_unverified_rate_card_estimate":
            raise EvidenceError("verifier success or local settlement absent")
        if record["gateway_pending"] != 0 or record["gateway_uncertain"] != 0 or record["gateway_breached"] is not False:
            raise EvidenceError("unsettled gateway obligations")
        calls, elapsed = record["gateway_recorded_calls"], record["harbor_reported_elapsed_seconds"]
        if type(calls) is not int or not 1 <= calls <= 10 or type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed <= 0:
            raise EvidenceError("invalid calls or duration")
        try:
            expense = Decimal(record["gateway_rate_card_estimate_usd"])
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise EvidenceError("invalid rate-card expense") from exc
        if not expense.is_finite() or not Decimal(0) < expense <= Decimal(1):
            raise EvidenceError("invalid rate-card expense")
        if record["provider_invoice_reconciled"] is not False or record["provider_spend_limit_verified"] is not False or record["verifier_independently_reexecuted"] is not False:
            raise EvidenceError("unsupported invoice or verifier replay claim")
        if record["publication_scope"] != "redacted_status_and_hashes_only":
            raise EvidenceError("invalid evidence publication scope")
        observations.append({"model":model,"gateway_calls":calls,"elapsed_seconds":elapsed,"rate_card_estimate_usd":format(expense,"f"),"harbor_verifier":"pass"})
    if seen != ALLOWED or len(tasks) != 1:
        raise EvidenceError("different task or incomplete model panel")
    return {"source_run":manifest["source_run"],"task_checksum":next(iter(tasks)),
            "observations":observations,"eligible_for_ranking":False,
            "provider_invoice_reconciled":False,"verifier_independently_reexecuted":False}

if __name__ == "__main__":
    try:
        print(json.dumps(validate(Path(__file__).resolve().parents[1]),sort_keys=True,indent=2))
    except (OSError, EvidenceError) as exc:
        print(f"evidence validation failed: {exc}",file=sys.stderr)
        raise SystemExit(2) from exc
