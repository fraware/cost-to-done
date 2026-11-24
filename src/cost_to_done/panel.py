"""Freeze a matched, bounded development panel without any model requests.

This planner describes experiments; it neither authorizes paid execution nor
establishes that the public development fixtures represent external workloads.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .gateway import PriceSchedule
from .ledger import _units, _usd
from .live import HARBOR_VERSION, PI_VERSION, TRUSTED_TASK_MODULES, staged_task_inputs

CONFIGURATIONS = {
    "terra-low": ("gpt-6.1-terra", "experiments/live/prices-gpt-6.1-terra-2026-11-23.json"),
    "sol-low": ("gpt-6.2-sol", "experiments/live/prices-gpt-6.2-sol-2026-11-23.json"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _file_record(root: Path, file: Path) -> dict[str, Any]:
    if (not file.is_file() or file.is_symlink() or file.resolve() != file
            or not file.is_relative_to(root) or file.stat().st_size > 20_000_000):
        raise ReceiptError("missing, oversized or unsafe panel input")
    return {"sha256": _sha(file.read_bytes()), "executable": bool(file.stat().st_mode & 0o111)}


def build_panel(root: Path, *, repetitions: int = 1, seed: int = 20261124,
                budget_per_trial: str = "1", max_total_usd: str = "6") -> dict[str, Any]:
    """Return an exact prospective run list with matched support and input hashes.

    Every task/repetition pair is adjacent in the schedule. Configuration order
    alternates across shuffled blocks, reducing systematic order imbalance.
    The manifest records file identities, not a claim of runtime image binding.
    """
    if type(repetitions) is not int or not 1 <= repetitions <= 10:
        raise ReceiptError("repetitions must be an integer from 1 to 10")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ReceiptError("seed must be an unsigned 32-bit integer")
    budget = _units(budget_per_trial, allow_zero=False)
    ceiling = _units(max_total_usd, allow_zero=False)
    count = len(CONFIGURATIONS) * len(TRUSTED_TASK_MODULES) * repetitions
    total = count * budget
    if total > ceiling:
        raise ReceiptError("panel admission allowances exceed the declared aggregate ceiling")
    if root.is_symlink():
        raise ReceiptError("repository root must not be a symlink")
    root = root.resolve(strict=True)
    tasks: dict[str, Any] = {}
    for task_name in sorted(TRUSTED_TASK_MODULES):
        task = root / "tasks" / task_name
        paths, dockerfile = staged_task_inputs(root, task)
        records = {name: _file_record(root, task / name) for name in paths}
        records["environment/Dockerfile"] = {
            "sha256": _sha(dockerfile), "executable": False,
        }
        tasks[task_name] = {"staged_files": records, "staged_input_sha256": _sha(_canonical(records))}
    configs = {}
    for name, (model, price_path) in sorted(CONFIGURATIONS.items()):
        price_file = root / price_path
        _file_record(root, price_file)
        price = PriceSchedule.load(price_file)
        if price.model != model:
            raise ReceiptError("panel price schedule does not match model")
        configs[name] = {"model": model, "api": "responses", "reasoning_effort": "low",
                         "price_schedule": price_path, "price_schedule_sha256": price.digest}
    source = sorted((root / "src/cost_to_done").glob("*.py"))
    if not source or not (root / "src/cost_to_done/live.py").is_file():
        raise ReceiptError("panel runner sources are missing")
    source.extend(root / p for p in ("experiments/live/compose.yaml",
                                    "experiments/live/base-compose-ci.yaml",
                                    "experiments/live/Dockerfile.pi",
                                    "scripts/run_development_panel.py",
                                    "scripts/run_real_model_smoke.py",
                                    ".github/workflows/development-panel.yml"))
    harness = {p.relative_to(root).as_posix(): _file_record(root, p) for p in source}
    blocks = [(task, rep) for task in tasks for rep in range(1, repetitions + 1)]
    rng = random.Random(seed)
    rng.shuffle(blocks)
    order = sorted(configs)
    rng.shuffle(order)
    trials = []
    for index, (task, rep) in enumerate(blocks):
        for configuration in (order if index % 2 == 0 else order[::-1]):
            trials.append({"trial_id": f"panel-{task}-{configuration}-r{rep:02d}",
                           "task": task, "configuration": configuration, "repetition": rep,
                           "estimated_admission_allowance_usd": _usd(budget)})
    result = {
        "schema_version": 1, "status": "plan_only", "scope": "public_development_fixtures",
        "seed": seed, "repetitions": repetitions, "planned_trial_count": count,
        "estimated_admission_total_usd": _usd(total), "declared_ceiling_usd": _usd(ceiling),
        "provider_hard_cap_verified": False, "paid_execution_authorized": False,
        "tasks": tasks, "configurations": configs,
        "harness": {"harbor_version": HARBOR_VERSION, "pi_version": PI_VERSION,
                    "max_turns": 5, "max_output_tokens": 4096, "max_wall_seconds": 900,
                    "attempts_per_trial": 1, "files": harness,
                    "source_manifest_sha256": _sha(_canonical(harness))},
        "trials": trials,
    }
    result["plan_sha256"] = _sha(_canonical(result))
    return result
