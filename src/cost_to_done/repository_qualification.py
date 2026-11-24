"""Local no-model qualification of two prepared repository snapshots.

The result binds the operator-supplied Harbor control records to both
manifests. This is not origin authentication or a secure attestation of
execution. Retain the raw job directories to independently inspect them.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .harbor import inspect_harbor_job
from .repository_task import validate_repository_task, _canonical


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _manifest(task: Path) -> dict:
    identity = validate_repository_task(task)
    path = task / "ctd-task-manifest.json"
    obj = json.loads(path.read_bytes())
    if obj.get("task_input_sha256") != identity["task_input_sha256"]:
        raise ReceiptError("prepared task manifest changed during qualification")
    return obj


def qualify_repository_task(starter: Path, reference: Path, starter_job: Path,
                            reference_job: Path) -> dict:
    """Require matching tests, instructions, source support and opposed controls."""
    left, right = _manifest(starter), _manifest(reference)
    if starter.resolve() == reference.resolve() or starter_job.resolve() == reference_job.resolve():
        raise ReceiptError("starter and reference controls must be distinct")
    if left["git_commit"] == right["git_commit"] or left["task"] != right["task"]:
        raise ReceiptError("controls must use distinct commits of the same declared task")
    if set(left["files"]) != set(right["files"]):
        raise ReceiptError("control file support mismatch")
    if [(x["repository_path"], x["role"], x["staged_path"]) for x in left["source_and_test_objects"]] != [
            (x["repository_path"], x["role"], x["staged_path"]) for x in right["source_and_test_objects"]]:
        raise ReceiptError("control repository path support mismatch")
    shared = sorted(p for p in left["files"] if not p.startswith("environment/workspace/"))
    if any(left["files"][p] != right["files"][p] for p in shared):
        raise ReceiptError("controls must use identical tests, instruction and runtime wrapper")
    if all(left["files"][p] == right["files"][p] for p in left["files"] if p not in shared):
        raise ReceiptError("reference source must differ from starter")
    rows = []
    for task, job, manifest, expected in ((starter, starter_job, left, "fail"),
                                          (reference, reference_job, right, "pass")):
        inspected = inspect_harbor_job(job)
        if inspected.get("complete") is not True or inspected.get("observed_trials") != 1:
            raise ReceiptError("expected one completed Harbor nop trial per control")
        trial = inspected["trials"][0]
        if (trial["agent"] != "nop" or trial["model"] is not None
                or trial["outcome"] != expected
                or not _digest(trial["raw_result_sha256"]) or not _digest(trial["task_checksum"])):
            raise ReceiptError("unexpected Harbor no-model control result")
        # Harbor reports the task's declared name. Retain its checksum separately
        # from the packaging manifest: the formats are not interchangeable.
        if trial["task"] not in (task.name, "cost-to-done/" + manifest["task"]):
            raise ReceiptError("control task name does not match declared task")
        rows.append({"outcome": expected, "git_commit": manifest["git_commit"],
                     "task_input_sha256": manifest["task_input_sha256"],
                     "harbor_task_checksum": trial["task_checksum"],
                     "harbor_raw_result_sha256": trial["raw_result_sha256"]})
    if (rows[0]["harbor_raw_result_sha256"] == rows[1]["harbor_raw_result_sha256"]
            or rows[0]["harbor_task_checksum"] == rows[1]["harbor_task_checksum"]):
        raise ReceiptError("control result or task identity unexpectedly repeated")
    result = {"schema_version": 1, "status": "repository_task_controls_agree",
              "scope": "operator_supplied_local_harbor_nop_controls",
              "task": left["task"], "starter": rows[0], "reference": rows[1],
              "shared_input_sha256": _sha(_canonical({p: left["files"][p] for p in shared})),
              "provider_calls": 0, "origin_authenticated": False,
              "paid_execution_authorized": False}
    result["qualification_sha256"] = _sha(_canonical(result))
    return result


def check_qualification(task: Path, receipt_path: Path, expected_digest: str) -> dict:
    """Validate a local receipt and bind it to the separately pinned starter."""
    identity = validate_repository_task(task)
    if not _digest(expected_digest) or identity["task_input_sha256"] != expected_digest:
        raise ReceiptError("prepared task differs from separately pinned task digest")
    if (receipt_path.is_symlink() or not receipt_path.is_file()
            or receipt_path.stat().st_size > 128_000):
        raise ReceiptError("unsafe qualification receipt")
    receipt = json.loads(receipt_path.read_bytes())
    if not isinstance(receipt, dict):
        raise ReceiptError("qualification receipt must be an object")
    if (receipt.get("schema_version") != 1
            or receipt.get("status") != "repository_task_controls_agree"
            or receipt.get("scope") != "operator_supplied_local_harbor_nop_controls"
            or receipt.get("task") != identity["task"]
            or receipt.get("origin_authenticated") is not False
            or receipt.get("paid_execution_authorized") is not False
            or type(receipt.get("provider_calls")) is not int or receipt["provider_calls"] != 0
            or receipt.get("qualification_sha256") != _sha(_canonical(
                {k: v for k, v in receipt.items() if k != "qualification_sha256"}))):
        raise ReceiptError("invalid repository qualification receipt")
    starter, reference = receipt.get("starter"), receipt.get("reference")
    if not isinstance(starter, dict) or not isinstance(reference, dict):
        raise ReceiptError("missing control observations")
    if (starter.get("task_input_sha256") != expected_digest
            or starter.get("git_commit") != identity["git_commit"]
            or starter.get("outcome") != "fail" or reference.get("outcome") != "pass"
            or starter.get("git_commit") == reference.get("git_commit")
            or starter.get("task_input_sha256") == reference.get("task_input_sha256")
            or starter.get("harbor_raw_result_sha256") == reference.get("harbor_raw_result_sha256")
            or starter.get("harbor_task_checksum") == reference.get("harbor_task_checksum")
            or any(not _digest(row.get(field)) for row in (starter, reference)
                   for field in ("task_input_sha256", "harbor_raw_result_sha256", "harbor_task_checksum"))):
        raise ReceiptError("qualification controls do not bind the requested starter")
    manifest = _manifest(task)
    shared = {p: record for p, record in manifest["files"].items()
              if not p.startswith("environment/workspace/")}
    if receipt.get("shared_input_sha256") != _sha(_canonical(shared)):
        raise ReceiptError("qualification shared inputs differ from staged task")
    return receipt
