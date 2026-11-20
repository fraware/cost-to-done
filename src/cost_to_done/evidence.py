"""Conservatively bind one completed Harbor trial to one gateway cost ledger.

This is *artifact reconciliation*, not invoice reconciliation. A single-trial
ledger is necessary because the gateway does not yet cryptographically link
individual request IDs to Harbor trial IDs. Fictitious, local mock results are
also accepted, always labeled as rate-card estimates, never as billed expense.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from .core import ReceiptError, parse_trial
from .gateway import PriceSchedule
from .harbor import inspect_harbor_job
from .ledger import BudgetLedger


def _digest_file(path: Path) -> str:
    """Hash bytes from a regular, nonsymlink file, with an explicit size bound."""
    if path.is_symlink() or not path.is_file():
        raise ReceiptError(f"missing or symlinked artifact: {path}")
    if path.stat().st_size > 20_000_000:
        raise ReceiptError(f"oversized artifact: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_digest(root: Path) -> str:
    """Content-address the local task without exposing its oracle solution."""
    if root.is_symlink() or not root.is_dir():
        raise ReceiptError("task directory must be a real directory")
    root = root.resolve(strict=True)
    files = sorted(root.rglob("*"))
    digest = hashlib.sha256()
    included = 0
    for path in files:
        relative = path.relative_to(root)
        if relative.parts[0] == "solution":
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ReceiptError(f"unsafe task artifact: {relative}")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_size > 20_000_000:
            raise ReceiptError(f"unsupported task artifact: {relative}")
        raw = path.read_bytes()
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update((path.stat().st_mode & 0o111).to_bytes(2, "big"))
        digest.update(len(raw).to_bytes(8, "big") + raw)
        included += 1
    if not included:
        raise ReceiptError("task directory has no included files")
    return digest.hexdigest()


@dataclass(frozen=True)
class EvidenceRequest:
    """Explicit identities for one externally controlled evaluation episode."""

    job: Path
    ledger: Path
    task: Path
    verifier: Path
    price_schedule: Path
    configuration_id: str
    agent: str
    model: str
    harness_digest: str
    harbor_task_checksum: str


def inspect_evidence(request: EvidenceRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return canonical receipt and audit sidecar, without writing or running code.

    All ledger charges are attributed to the sole Harbor trial. This is only
    defensible when the operator has provided a *dedicated* ledger and can
    independently confirm that no other agent or process used its token.
    No cryptographic request-to-trial association or provider invoice proof is
    inferred from file contents.
    """
    if not isinstance(request.configuration_id, str) or not request.configuration_id.strip():
        raise ReceiptError("configuration_id is required")
    if not isinstance(request.agent, str) or not request.agent:
        raise ReceiptError("expected agent is required")
    if not isinstance(request.model, str) or not request.model:
        raise ReceiptError("expected provider/model is required")
    for name, value, size in (("harness_digest", request.harness_digest, 64),
                              ("harbor_task_checksum", request.harbor_task_checksum, 40)):
        if not isinstance(value, str) or len(value) != size or any(ch not in "0123456789abcdef" for ch in value):
            raise ReceiptError(f"{name} must be a lowercase {size}-character hex digest")
    if not request.model.startswith("openai/"):
        raise ReceiptError("current gateway evidence only supports an explicit openai/ route")
    task = request.task.resolve(strict=True)
    if request.task.is_symlink() or request.verifier.is_symlink():
        raise ReceiptError("task/verifier paths must not be symlinks")
    verifier = request.verifier.resolve(strict=True)
    if not verifier.is_relative_to(task):
        raise ReceiptError("verifier file must be within the supplied task tree")
    verifier_digest = _digest_file(verifier)
    task_digest = _task_digest(request.task)

    schedule = PriceSchedule.load(request.price_schedule)
    if request.model.split("/", 1)[1] != schedule.model:
        raise ReceiptError("priced model differs from requested model")
    result = inspect_harbor_job(request.job)
    if result.get("complete") is not True or result.get("observed_trials") != 1:
        raise ReceiptError("exactly one completed Harbor trial is necessary")
    trial = result["trials"][0]
    if (trial.get("model") != schedule.model or trial.get("provider") != "openai"
            or trial.get("agent") != request.agent):
        raise ReceiptError("Harbor model/provider/agent identity mismatch")
    if trial.get("task_checksum") != request.harbor_task_checksum:
        raise ReceiptError("Harbor task checksum differs from expected value")
    if trial.get("outcome") not in ("pass", "fail", "infrastructure_error"):
        raise ReceiptError("unsupported Harbor trial outcome")
    duration = trial.get("elapsed_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
        raise ReceiptError("invalid Harbor wall-clock duration")

    ledger = BudgetLedger(request.ledger)
    state = ledger.snapshot()
    if state.schedule_sha256 != schedule.digest:
        raise ReceiptError("ledger and price schedule digests differ")
    if state.pending or state.uncertain or state.reserved != "0" or state.breached:
        raise ReceiptError("ledger contains unresolved liability or breached its estimate")
    entries = ledger.entries()
    if not entries or any(x["state"] != "settled" or x["actual_usd"] is None for x in entries):
        raise ReceiptError("ledger needs one or more fully settled request entries")
    total = sum((Decimal(x["actual_usd"]) for x in entries), Decimal("0"))
    if total <= 0 or total != Decimal(state.settled):
        raise ReceiptError("ledger entry totals disagree with settled amount or are zero")
    receipt = {
        "trial_id": trial["id"],
        "configuration_id": request.configuration_id,
        "task_id": trial["task"],
        "task_digest": task_digest,
        "verifier_digest": verifier_digest,
        "harness_digest": request.harness_digest,
        "retry_policy": "independent-trials",
        "attempts": [{
            "cost_usd": state.settled,
            "seconds": duration,
            "outcome": trial["outcome"],
            "cost_source": "rate_card_estimate",
        }],
    }
    parse_trial(receipt)
    provenance = {
        "schema_version": 1,
        "evidence_kind": "single_harbor_trial_with_dedicated_gateway_ledger",
        "harbor_trial_id": trial["id"],
        "harbor_trial_raw_sha256": trial["raw_result_sha256"],
        "harbor_task_checksum": trial["task_checksum"],
        "price_schedule_sha256": schedule.digest,
        "gateway_ledger_file_sha256": _digest_file(request.ledger),
        "gateway_request_count": len(entries),
        "gateway_request_ids": [entry["request_id"] for entry in entries],
        "total_rate_card_estimate_usd": state.settled,
        "model_route": request.model,
        "billing_verified": False,
        "verifier_independently_audited": False,
        "request_to_trial_attribution": "single-dedicated-ledger-operator-assertion",
        "task_verifier_files_hashed_locally": True,
        "execution_image_binding_verified": False,
        "mock_or_real_model_determined": False,
    }
    return receipt, provenance


def write_evidence_receipt(request: EvidenceRequest, output: Path) -> dict[str, Any]:
    """Create a receipt and adjacent audit record; never overwrite evidence."""
    receipt, provenance = inspect_evidence(request)
    sidecar = output.with_name(output.name + ".evidence.json")
    if output == sidecar or output.exists() or sidecar.exists() or output.is_symlink() or sidecar.is_symlink():
        raise ReceiptError("receipt or evidence sidecar already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    temp_meta = sidecar.with_name(sidecar.name + ".tmp")
    if temp.exists() or temp_meta.exists():
        raise ReceiptError("temporary output exists; refusing overwrite")
    try:
        with temp.open("x", encoding="utf-8") as file:
            file.write(json.dumps(receipt, sort_keys=True, allow_nan=False) + "\n")
        with temp_meta.open("x", encoding="utf-8") as file:
            json.dump(provenance, file, sort_keys=True, indent=2, allow_nan=False)
            file.write("\n")
        # Filesystem rename protects each file individually. Atomic pair
        # publication is not possible, so audit tools require both files.
        temp_meta.replace(sidecar)
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
        temp_meta.unlink(missing_ok=True)
    return {"receipt": str(output), "evidence": str(sidecar),
            "trial_id": receipt["trial_id"], "cost_basis": "rate_card_estimate",
            "provider_invoice_reconciled": False}
