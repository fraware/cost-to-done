"""Conservative Harbor result importer.

Import only finished single-step trial results with nonmissing positive cost
attributions. Harbor's agent-reported cost is *estimated*, not a provider
invoice. Task/verifier identities and agent settings are specified in a local
manifest; their authenticity is outside this module's trust boundary.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .core import ReceiptError, parse_trial


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReceiptError(f"{name}: expected JSON object")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"{name}: expected nonempty string")
    return value


def _elapsed(raw: dict[str, Any]) -> float:
    """Use full trial wall-clock time, not isolated agent execution time."""
    try:
        start = datetime.fromisoformat(_text(raw.get("started_at"), "started_at"))
        finish = datetime.fromisoformat(_text(raw.get("finished_at"), "finished_at"))
        if start.tzinfo is None or finish.tzinfo is None:
            raise ValueError("timestamps must have offsets")
        duration = (finish - start).total_seconds()
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("negative/nonfinite duration")
        return duration
    except (ValueError, TypeError) as exc:
        raise ReceiptError(f"invalid trial timestamps: {exc}") from exc


def _agent_cost(raw: dict[str, Any]) -> Decimal:
    """Read Harbor's reported cost, summing step contexts for multi-step tasks."""
    if raw.get("agent_result") is not None:
        contexts = [_object(raw["agent_result"], "agent_result")]
    elif isinstance(raw.get("step_results"), list):
        contexts = [
            _object(step["agent_result"], "step agent_result")
            for step in raw["step_results"]
            if isinstance(step, dict) and step.get("agent_result") is not None
        ]
    else:
        contexts = []
    if not contexts:
        raise ReceiptError("missing agent_result cost: do not interpret as zero")
    amount = Decimal(0)
    for context in contexts:
        value = context.get("cost_usd")
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ReceiptError("missing or unsupported agent cost_usd")
        try:
            unit = Decimal(str(value))
        except ArithmeticError as exc:
            raise ReceiptError("invalid agent cost_usd") from exc
        if not unit.is_finite() or unit < 0:
            raise ReceiptError("negative/nonfinite agent cost")
        amount += unit
    # Allow 12 decimal places in the lossless public receipt schema.
    return amount.quantize(Decimal("0.000000000001"))


def _outcome(raw: dict[str, Any], *, reward_key: str) -> str:
    """Conservatively treat incomplete, errored or nongraded results as errors."""
    if raw.get("exception_info") is not None:
        return "infrastructure_error"
    steps = raw.get("step_results") or []
    if any(isinstance(step, dict) and step.get("exception_info") for step in steps):
        return "infrastructure_error"
    verifier = raw.get("verifier_result")
    if not isinstance(verifier, dict):
        return "infrastructure_error"
    rewards = verifier.get("rewards")
    if not isinstance(rewards, dict) or reward_key not in rewards:
        return "infrastructure_error"
    reward = rewards[reward_key]
    if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not math.isfinite(reward):
        raise ReceiptError("invalid verifier reward")
    if reward < 0 or reward > 1:
        raise ReceiptError("verifier reward outside [0,1]")
    return "pass" if reward == 1 else "fail"


def import_harbor(manifest_file: Path) -> list[dict[str, Any]]:
    """Normalize locally stored Harbor trial results under explicit pinning.

    A manifest has a list of jobs and a dictionary of task provenance. All
    result paths are confined to their declared job directories; symlinked
    trial result files are rejected. Only single-attempt job results are
    imported, preserving each independently graded trial as one episode.
    """
    manifest_file = manifest_file.resolve()
    manifest = _object(json.loads(manifest_file.read_text(encoding="utf-8")), "manifest")
    if manifest.get("schema_version") != 1:
        raise ReceiptError("manifest schema_version must be 1")
    tasks = _object(manifest.get("tasks"), "tasks")
    jobs = manifest.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ReceiptError("jobs: expected nonempty list")
    out: list[dict[str, Any]] = []
    for job in jobs:
        job = _object(job, "job")
        relative = _text(job.get("path"), "job.path")
        job_path = (manifest_file.parent / relative).resolve()
        if not job_path.is_dir():
            raise ReceiptError(f"missing job directory: {relative}")
        config_id = _text(job.get("configuration_id"), "configuration_id")
        expected_agent = _text(job.get("agent"), "job.agent")
        expected_model = _text(job.get("model"), "job.model")
        if job.get("n_attempts") != 1:
            raise ReceiptError("one Harbor attempt per independent trial is required")
        if job.get("retry_policy") != "independent-trials":
            raise ReceiptError("retry_policy must be independent-trials")
        digest = _text(job.get("harness_digest"), "harness_digest")
        trial_files = sorted(job_path.glob("trials/*/result.json"))
        if not trial_files:
            raise ReceiptError(f"no completed Harbor trials in {relative}")
        for path in trial_files:
            if path.is_symlink() or not path.resolve().is_relative_to(job_path):
                raise ReceiptError(f"unsafe trial path: {path}")
            raw = _object(json.loads(path.read_text(encoding="utf-8")), "Harbor result")
            task_name = _text(raw.get("task_name"), "task_name")
            source = _object(tasks.get(task_name), f"task {task_name} manifest")
            if raw.get("task_checksum") != source.get("harbor_task_checksum"):
                raise ReceiptError(f"{task_name}: Harbor checksum differs from manifest")
            info = _object(raw.get("agent_info"), "agent_info")
            model_info = _object(info.get("model_info"), "model_info")
            provider = model_info.get("provider")
            actual_model = f"{provider}/{model_info.get('name')}" if provider else model_info.get("name")
            if info.get("name") != expected_agent or actual_model != expected_model:
                raise ReceiptError(f"{path}: agent/model mismatch")
            reward_key = _text(source.get("reward_key", "reward"), "reward_key")
            obj = {
                "trial_id": _text(raw.get("id"), "id"),
                "configuration_id": config_id,
                "task_id": task_name,
                "task_digest": source.get("task_digest"),
                "verifier_digest": source.get("verifier_digest"),
                "harness_digest": digest,
                "retry_policy": "independent-trials",
                "attempts": [{
                    "cost_usd": str(_agent_cost(raw)),
                    "seconds": _elapsed(raw),
                    "outcome": _outcome(raw, reward_key=reward_key),
                    "cost_source": "rate_card_estimate",
                }],
            }
            parse_trial(obj)
            out.append(obj)
    if len({row["trial_id"] for row in out}) != len(out):
        raise ReceiptError("duplicate imported Harbor trial IDs")
    return out


def write_harbor_receipts(manifest: Path, output: Path) -> int:
    """Atomically write normalized receipts; leave no partial files on failure."""
    rows = import_harbor(manifest)
    if output.exists():
        raise ReceiptError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise ReceiptError(f"temporary output already exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            for row in rows:
                file.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return len(rows)
