"""Task-level receipt validation and paired cost-performance estimates.

A trial is a complete attempt to finish one task, possibly containing multiple
charged agent attempts under a specified retry policy. Distinct task IDs, not
replicate trials, are the bootstrap resampling unit.
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any

_HASH = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED = {"pass", "fail", "infrastructure_error"}
_COST_SOURCES = {"billed", "rate_card_estimate"}
_DECIMAL_USD = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?$")


class ReceiptError(ValueError):
    """The input violates the receipt format or evaluation invariants."""


@dataclass(frozen=True)
class Attempt:
    cost: Decimal
    seconds: float
    outcome: str
    cost_source: str


@dataclass(frozen=True)
class Trial:
    trial_id: str
    task_id: str
    configuration_id: str
    task_digest: str
    verifier_digest: str
    harness_digest: str
    retry_policy: str
    attempts: tuple[Attempt, ...]

    @property
    def passed(self) -> bool:
        return self.attempts[-1].outcome == "pass"

    @property
    def cost(self) -> Decimal:
        return sum((a.cost for a in self.attempts), Decimal("0"))

    @property
    def seconds(self) -> float:
        return sum(a.seconds for a in self.attempts)

    @property
    def sources(self) -> set[str]:
        return {a.cost_source for a in self.attempts}


def _string(obj: dict[str, Any], field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ReceiptError(f"{field}: expected a nonempty string (max 256 characters)")
    return value


def _hash(obj: dict[str, Any], field: str) -> str:
    value = _string(obj, field)
    if not _HASH.fullmatch(value):
        raise ReceiptError(f"{field}: expected lowercase SHA-256 hex digest")
    return value


def _cost(value: Any) -> Decimal:
    # Require an exact decimal *string*; avoid binary floating-point and silent
    # loss of precision in micro-dollar charges.
    if not isinstance(value, str):
        raise ReceiptError("cost_usd: expected a quoted decimal string")
    if not _DECIMAL_USD.fullmatch(value):
        raise ReceiptError("cost_usd: use plain nonnegative decimal USD with up to 12 fractional digits")
    try:
        cost = Decimal(value)
    except InvalidOperation as exc:
        raise ReceiptError("cost_usd: invalid decimal") from exc
    if not cost.is_finite() or cost < 0:
        raise ReceiptError("cost_usd: must be finite and nonnegative")
    if -cost.as_tuple().exponent > 12:
        raise ReceiptError("cost_usd: maximum 12 decimal places")
    return cost


def parse_trial(obj: Any) -> Trial:
    """Validate one immutable receipt; reject post-success charged attempts."""
    if not isinstance(obj, dict):
        raise ReceiptError("expected JSON object per line")
    fields = {name: _string(obj, name) for name in (
        "trial_id", "task_id", "configuration_id", "retry_policy"
    )}
    digests = {name: _hash(obj, name) for name in (
        "task_digest", "verifier_digest", "harness_digest"
    )}
    raw = obj.get("attempts")
    if not isinstance(raw, list) or not raw or len(raw) > 50:
        raise ReceiptError("attempts: expected 1 to 50 entries")
    attempts = []
    for number, a in enumerate(raw, 1):
        if not isinstance(a, dict):
            raise ReceiptError(f"attempt {number}: expected object")
        outcome = a.get("outcome")
        if outcome not in _ALLOWED:
            raise ReceiptError(f"attempt {number}: unknown outcome {outcome!r}")
        source = a.get("cost_source")
        if source not in _COST_SOURCES:
            raise ReceiptError(f"attempt {number}: cost_source must be billed or rate_card_estimate")
        seconds = a.get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise ReceiptError(f"attempt {number}: seconds must be finite and nonnegative")
        if attempts and attempts[-1].outcome == "pass":
            raise ReceiptError("no further attempts permitted once verified success occurs")
        attempts.append(Attempt(_cost(a.get("cost_usd")), float(seconds), outcome, source))
    return Trial(**fields, **digests, attempts=tuple(attempts))


def read_trials(path: str | Path) -> list[Trial]:
    """Load a JSONL file, retaining the row number in validation failures."""
    trials = []
    seen = set()
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if len(line) > 1_000_000:
                raise ReceiptError(f"line {line_no}: exceeds 1 MB input limit")
            if not line.strip():
                continue
            try:
                trial = parse_trial(json.loads(line))
                if trial.trial_id in seen:
                    raise ReceiptError(f"duplicate trial_id {trial.trial_id}")
                seen.add(trial.trial_id)
                trials.append(trial)
            except (json.JSONDecodeError, ReceiptError) as exc:
                raise ReceiptError(f"line {line_no}: {exc}") from exc
    if not trials:
        raise ReceiptError("input contains no trial records")
    return trials


def _ratio(block: list[Trial]) -> float:
    passed = sum(t.passed for t in block)
    return float(sum((t.cost for t in block), Decimal("0")) / passed) if passed else math.inf


def _paired_task_bootstrap(trials: list[Trial], configs: list[str], task_ids: list[str], draws: int = 2000) -> dict[str, tuple[float, float]]:
    """Percentile intervals from task-cluster bootstrap; infinity is unbounded.

    The reported intervals are descriptive, not a multiple-comparison-adjusted
    statistical test or a guarantee about generalization to unseen repositories.
    """
    by_key: dict[tuple[str, str], list[Trial]] = defaultdict(list)
    for trial in trials:
        by_key[(trial.configuration_id, trial.task_id)].append(trial)
    samples = {name: [] for name in configs}
    rand = random.Random(20261120)
    for _ in range(draws):
        selected = rand.choices(task_ids, k=len(task_ids))
        for name in configs:
            observations = [t for task in selected for t in by_key[(name, task)]]
            samples[name].append(_ratio(observations))
    intervals = {}
    for name, values in samples.items():
        values.sort()
        intervals[name] = (values[int(0.025 * (draws - 1))], values[int(0.975 * (draws - 1))])
    return intervals


def analyze(trials: list[Trial]) -> dict[str, Any]:
    """Summarize attempts and withhold ranking for unmatched trial designs."""
    by_config: dict[str, list[Trial]] = defaultdict(list)
    definition: dict[str, tuple[str, str]] = {}
    harness: dict[str, str] = {}
    policies: dict[str, str] = {}
    warnings: list[str] = []
    for t in trials:
        by_config[t.configuration_id].append(t)
        if t.task_id in definition and definition[t.task_id] != (t.task_digest, t.verifier_digest):
            raise ReceiptError(f"task {t.task_id}: task/verifier digests differ across trials")
        definition[t.task_id] = (t.task_digest, t.verifier_digest)
        if t.configuration_id in harness and harness[t.configuration_id] != t.harness_digest:
            raise ReceiptError(f"configuration {t.configuration_id}: mixed harness digests")
        harness[t.configuration_id] = t.harness_digest
        if t.configuration_id in policies and policies[t.configuration_id] != t.retry_policy:
            raise ReceiptError(f"configuration {t.configuration_id}: mixed retry policies")
        policies[t.configuration_id] = t.retry_policy
    configs = sorted(by_config)
    # Compare the identical task IDs, verification definitions, and replicate counts.
    signatures = []
    for config in configs:
        counts: dict[str, int] = defaultdict(int)
        for t in by_config[config]:
            counts[t.task_id] += 1
        signatures.append(tuple(sorted(counts.items())))
    matched = len(set(signatures)) == 1
    if not matched:
        warnings.append("Configurations do not cover identical task IDs with identical numbers of trials. No comparative ranking or confidence intervals are produced.")
    if len(set(policies.values())) > 1:
        warnings.append("Retry policies differ. Monetary rankings are withheld because the compared configurations use different execution policies.")
        matched = False
    cost_sources = {c: set().union(*(t.sources for t in group)) for c, group in by_config.items()}
    if len(set(tuple(sorted(s)) for s in cost_sources.values())) > 1 or any(len(s) != 1 for s in cost_sources.values()):
        warnings.append("Billed and/or estimated expenses are mixed. Monetary rankings are withheld until a common cost basis is established.")
        matched = False
    task_ids = sorted(definition)
    if len(task_ids) < 5:
        warnings.append("Fewer than five distinct tasks: exploratory results only; no task-bootstrap intervals.")
    confidence_intervals = (_paired_task_bootstrap(trials, configs, task_ids)
                            if matched and len(task_ids) >= 5 else {})
    rows = []
    for config in configs:
        group = by_config[config]
        passed = sum(t.passed for t in group)
        spend = sum((t.cost for t in group), Decimal("0"))
        row = {
            "configuration": config,
            "trials": len(group),
            "passed": passed,
            "pass_rate": passed / len(group),
            "total_cost_usd": str(spend),
            "cost_per_success_usd": str(spend / passed) if passed else None,
            "median_seconds": median(t.seconds for t in group),
            "attempts": sum(len(t.attempts) for t in group),
            "infra_attempts": sum(a.outcome == "infrastructure_error" for t in group for a in t.attempts),
            "cost_basis": ", ".join(sorted(cost_sources[config])),
            "harness_digest": harness[config],
            "retry_policy": policies[config],
        }
        if config in confidence_intervals:
            lo, hi = confidence_intervals[config]
            row["bootstrap_95_usd"] = [lo if math.isfinite(lo) else None, hi if math.isfinite(hi) else None]
        rows.append(row)
    if matched:
        rows.sort(key=lambda r: (float(r["cost_per_success_usd"]) if r["cost_per_success_usd"] is not None else math.inf, r["configuration"]))
    return {"eligible_for_ranking": matched, "tasks": len(task_ids), "trials": len(trials), "warnings": warnings, "rows": rows}
