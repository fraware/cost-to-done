"""Conservative Harbor result importer.

Import only finished single-step trial results with nonmissing positive cost
attributions. Harbor's agent-reported cost is *estimated*, not a provider
invoice. Task/verifier identities and agent settings are specified in a local
manifest; their authenticity is outside this module's trust boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .core import ReceiptError, parse_trial
from .private_files import publish_private_texts


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
        if isinstance(value, str) and len(value) > 64:
            raise ReceiptError("agent cost has an excessive decimal representation")
        try:
            unit = Decimal(str(value))
        except ArithmeticError as exc:
            raise ReceiptError("invalid agent cost_usd") from exc
        if not unit.is_finite() or unit < 0:
            raise ReceiptError("negative/nonfinite agent cost")
        try:
            amount += unit
        except InvalidOperation as exc:
            raise ReceiptError("agent cost exceeds the supported decimal range") from exc
    # Harbor estimates are quantized to the public receipt's 12-place limit.
    # Keep nonzero microcharges nonzero; never silently turn a positive cost
    # into a zero-cost task, and reject unrepresentable extreme magnitudes.
    try:
        rounded = amount.quantize(Decimal("0.000000000001"))
    except InvalidOperation as exc:
        raise ReceiptError("agent cost exceeds the supported receipt precision") from exc
    if amount > 0 and rounded == 0:
        raise ReceiptError("positive agent cost is below the 12-place receipt precision")
    return rounded


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


def _trial_files(job_path: Path) -> list[Path]:
    """Discover trial results in Harbor's current or legacy on-disk layout.

    Avoid the root job-level result.json, which is a *summary* rather than a
    scored trial; mixed layouts and symlinked paths are not accepted.
    """
    modern = sorted(job_path.glob("*/result.json"))
    legacy = sorted(job_path.glob("trials/*/result.json"))
    if modern and legacy:
        raise ReceiptError(f"{job_path}: mixed Harbor trial layouts")
    files = modern or legacy
    if not files:
        raise ReceiptError(f"{job_path}: no completed Harbor trial results")
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(job_path):
            raise ReceiptError(f"{path}: unsafe trial path")
    return files


def inspect_harbor_job(job_dir: Path, *, reward_key: str = "reward") -> dict[str, Any]:
    """Describe real Harbor trial files without claiming verifier trust or billing.

    The result contains declared agent identity, reported verifier result,
    agent-reported monetary estimates (if available), and the SHA-256 hash of
    each on-disk JSON document. It executes no task code or provider calls.
    """
    if not reward_key or len(reward_key) > 256:
        raise ReceiptError("reward_key must be a nonempty string (max 256 chars)")
    if job_dir.is_symlink():
        raise ReceiptError("job directory must not be a symlink")
    root = job_dir.resolve(strict=True)
    if not root.is_dir():
        raise ReceiptError("job directory must be a directory")
    paths = _trial_files(root)
    rows: list[dict[str, Any]] = []
    for path in paths:
        data = path.read_bytes()
        raw = _object(json.loads(data.decode("utf-8")), "Harbor trial")
        if raw.get("schema_version", 1) != 1:
            raise ReceiptError(f"{path}: unsupported Harbor trial schema_version")
        agent = _object(raw.get("agent_info"), "agent_info")
        model = agent.get("model_info")
        if model is not None:
            model = _object(model, "model_info")
        contexts = (
            [raw["agent_result"]] if raw.get("agent_result") is not None else
            [step.get("agent_result") for step in raw.get("step_results") or []]
        )
        has_cost = bool(contexts) and all(
            isinstance(context, dict) and context.get("cost_usd") is not None
            for context in contexts
        )
        cost = format(_agent_cost(raw), "f") if has_cost else None
        rows.append({
            "id": _text(raw.get("id"), "trial id"),
            "task": _text(raw.get("task_name"), "task_name"),
            "task_checksum": _text(raw.get("task_checksum"), "task_checksum"),
            "agent": _text(agent.get("name"), "agent.name"),
            "agent_version": _text(agent.get("version"), "agent.version"),
            "model": model.get("name") if model is not None else None,
            "provider": model.get("provider") if model is not None else None,
            "outcome": _outcome(raw, reward_key=reward_key),
            "elapsed_seconds": _elapsed(raw),
            "agent_reported_cost_usd": cost,
            "cost_status": "agent_reported_estimate" if cost is not None else "unavailable",
            "raw_result_sha256": hashlib.sha256(data).hexdigest(),
        })
    summary = root / "result.json"
    expected_trials: int | None = None
    if summary.is_file() and not summary.is_symlink():
        obj = _object(json.loads(summary.read_text(encoding="utf-8")), "Harbor job summary")
        count = obj.get("n_total_trials")
        if type(count) is int and count >= 0:
            expected_trials = count
    return {
        "job": root.name,
        "observed_trials": len(rows),
        "expected_trials": expected_trials,
        "complete": expected_trials == len(rows) if expected_trials is not None else None,
        "billing_verified": False,
        "verifier_independently_audited": False,
        "trials": rows,
    }


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
    manifest_dir = manifest_file.parent
    for job in jobs:
        job = _object(job, "job")
        relative = _text(job.get("path"), "job.path")
        safe_path = Path(relative)
        if safe_path.is_absolute() or ".." in safe_path.parts or safe_path == Path("."):
            raise ReceiptError(f"job.path must be a relative child directory: {relative}")
        job_path = (manifest_dir / safe_path).resolve()
        if not job_path.is_relative_to(manifest_dir) or not job_path.is_dir():
            raise ReceiptError(f"unsafe or missing job directory: {relative}")
        config_id = _text(job.get("configuration_id"), "configuration_id")
        expected_agent = _text(job.get("agent"), "job.agent")
        expected_model = _text(job.get("model"), "job.model")
        if job.get("n_attempts") != 1:
            raise ReceiptError("one Harbor attempt per independent trial is required")
        if job.get("retry_policy") != "independent-trials":
            raise ReceiptError("retry_policy must be independent-trials")
        digest = _text(job.get("harness_digest"), "harness_digest")
        trial_files = _trial_files(job_path)
        expected = job.get("expected_tasks")
        if expected is not None:
            if (not isinstance(expected, list) or not expected
                    or len(expected) != len(set(map(str, expected)))
                    or any(not isinstance(x, str) or not x for x in expected)):
                raise ReceiptError("expected_tasks: expected distinct nonempty task names")
            if len(trial_files) != len(expected):
                raise ReceiptError(f"incomplete job {relative}: {len(trial_files)} results for {len(expected)} expected tasks")
        seen_tasks: set[str] = set()
        for path in trial_files:
            raw = _object(json.loads(path.read_text(encoding="utf-8")), "Harbor result")
            if raw.get("schema_version", 1) != 1:
                raise ReceiptError(f"{path}: unsupported Harbor trial schema_version")
            task_name = _text(raw.get("task_name"), "task_name")
            if task_name in seen_tasks:
                raise ReceiptError(f"{relative}: duplicate task {task_name} within one independent-trial job")
            seen_tasks.add(task_name)
            source = _object(tasks.get(task_name), f"task {task_name} manifest")
            if raw.get("task_checksum") != source.get("harbor_task_checksum"):
                raise ReceiptError(f"{task_name}: Harbor checksum differs from manifest")
            info = _object(raw.get("agent_info"), "agent_info")
            model_info = _object(info.get("model_info"), "model_info")
            provider = model_info.get("provider")
            actual_model = f"{provider}/{model_info.get('name')}" if provider else model_info.get("name")
            if info.get("name") != expected_agent or actual_model != expected_model:
                raise ReceiptError(f"{path}: agent/model mismatch")
            expected_version = job.get("agent_version")
            if expected_version is not None and info.get("version") != expected_version:
                raise ReceiptError(f"{path}: agent version mismatch")
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
                    "cost_usd": format(_agent_cost(raw), "f"),
                    "seconds": _elapsed(raw),
                    "outcome": _outcome(raw, reward_key=reward_key),
                    "cost_source": "rate_card_estimate",
                }],
            }
            parse_trial(obj)
            out.append(obj)
        if expected is not None and seen_tasks != set(expected):
            raise ReceiptError(f"incomplete job {relative}: task set differs from expected_tasks")
    if len({row["trial_id"] for row in out}) != len(out):
        raise ReceiptError("duplicate imported Harbor trial IDs")
    return out


def write_harbor_receipts(manifest: Path, output: Path) -> int:
    """Publish normalized receipts privately, atomically and without overwrite."""
    rows = import_harbor(manifest)
    payload = "".join(
        json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows
    )
    publish_private_texts([(output, payload)])
    return len(rows)
