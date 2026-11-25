"""Prospective, credential-free matched trial scheduling for the flagship study.

Input commitments refer to separately reviewed private evidence. This module
checks design structure and accounting bounds, not authenticity, consent,
verifier integrity, actual pricing, or provider-side budget enforcement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from cost_to_done.core import ReceiptError
from cost_to_done.ledger import _units, _usd
from cost_to_done.private_files import publish_private_texts

ID = re.compile(r"[a-z][a-z0-9-]{1,47}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
TASK_COUNT = 20
CONFIG_COUNT = 5
REPETITIONS = 3
STRATA = {"algorithm", "state", "parsing", "integration"}


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def exact_fields(obj: Any, fields: set[str]) -> dict:
    if not isinstance(obj, dict) or set(obj) != fields:
        raise ReceiptError(f"expected exactly these fields: {sorted(fields)}")
    return obj


def checked(value: Any, pattern: re.Pattern) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ReceiptError("invalid identifier or commitment digest")
    return value


def balanced_orders(configs: list[str]) -> list[list[str]]:
    """Williams design for five treatments: all rotations and their reversals.

    Over ten orders each configuration occupies each position twice and each
    directed adjacent pair occurs twice. This balances first-order carryover
    in the planned sequence; actual provider conditions remain uncontrolled.
    """
    if len(configs) != CONFIG_COUNT or len(set(configs)) != CONFIG_COUNT:
        raise ReceiptError("exactly five distinct configurations required")
    base = (0, 1, 4, 2, 3)
    forward = [[configs[(x + shift) % CONFIG_COUNT] for x in base]
               for shift in range(CONFIG_COUNT)]
    return forward + [list(reversed(order)) for order in forward]


def build_plan(spec: dict) -> dict:
    """Validate declared commitments and freeze all 300 planned trial IDs."""
    exact_fields(spec, {"schema_version", "seed", "tasks", "configurations",
                       "screening_log_sha256", "harness_sha256",
                       "retry_policy_sha256", "analysis_protocol_sha256",
                       "allowance_per_trial_usd", "max_total_usd"})
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1:
        raise ReceiptError("unsupported design schema")
    seed = spec["seed"]
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ReceiptError("seed must be a uint32")
    for field in ("screening_log_sha256", "harness_sha256",
                  "retry_policy_sha256", "analysis_protocol_sha256"):
        checked(spec[field], SHA)
    if not isinstance(spec["tasks"], list) or len(spec["tasks"]) != TASK_COUNT:
        raise ReceiptError("twenty tasks required")
    if not isinstance(spec["configurations"], list) or len(spec["configurations"]) != CONFIG_COUNT:
        raise ReceiptError("five configurations required")
    tasks = {}
    groups = Counter()
    strata = Counter()
    for raw in spec["tasks"]:
        row = exact_fields(raw, {"id", "repository_group", "stratum",
                                 "task_input_sha256", "qualification_sha256",
                                 "permission_record_sha256", "holdout_record_sha256"})
        ident = checked(row["id"], ID)
        group = checked(row["repository_group"], ID)
        stratum = row["stratum"]
        if not isinstance(stratum, str) or stratum not in STRATA or ident in tasks:
            raise ReceiptError("invalid stratum or repeated task ID")
        for field in ("task_input_sha256", "qualification_sha256",
                      "permission_record_sha256", "holdout_record_sha256"):
            checked(row[field], SHA)
        tasks[ident] = dict(row)
        groups[group] += 1
        strata[stratum] += 1
    if len(groups) < 5 or max(groups.values()) > 4:
        raise ReceiptError("at least five repository groups, maximum four tasks per group")
    if any(strata[s] != 5 for s in STRATA):
        raise ReceiptError("exactly five tasks per declared stratum required")
    for field in ("task_input_sha256", "qualification_sha256"):
        if len({r[field] for r in tasks.values()}) != TASK_COUNT:
            raise ReceiptError(f"duplicate task commitment: {field}")
    configs = {}
    for raw in spec["configurations"]:
        row = exact_fields(raw, {"id", "model", "configuration_sha256",
                                 "price_schedule_sha256", "route_qualification_sha256"})
        ident = checked(row["id"], ID)
        if ident in configs or not isinstance(row["model"], str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", row["model"]):
            raise ReceiptError("invalid or repeated configuration identity")
        for field in ("configuration_sha256", "price_schedule_sha256",
                      "route_qualification_sha256"):
            checked(row[field], SHA)
        configs[ident] = dict(row)
    if len({r["configuration_sha256"] for r in configs.values()}) != CONFIG_COUNT:
        raise ReceiptError("duplicate configuration commitments")
    allowance = _units(spec["allowance_per_trial_usd"], allow_zero=False)
    ceiling = _units(spec["max_total_usd"], allow_zero=False)
    count = TASK_COUNT * CONFIG_COUNT * REPETITIONS
    total = count * allowance
    if total > ceiling:
        raise ReceiptError("aggregate estimated admission allowances exceed declared ceiling")

    def key(domain: str, value: Any) -> tuple[str, str]:
        return digest([domain, seed, value]), str(value)

    blocks = sorted([(t, r) for t in tasks for r in range(1, REPETITIONS + 1)],
                    key=lambda b: key("task-block", b))
    ordered_configs = sorted(configs, key=lambda c: key("treatment", c))
    orders = balanced_orders(ordered_configs)
    # Each ten-block cycle contains every balanced order exactly once.
    schedule = []
    for index, (task, repetition) in enumerate(blocks):
        cycle = index // len(orders)
        perm = sorted(range(len(orders)), key=lambda i: key("order-cycle", [cycle, i]))
        order = orders[perm[index % len(orders)]]
        for position, config in enumerate(order, 1):
            schedule.append({"trial_id": f"{task}:{config}:r{repetition}",
                             "task": task, "configuration": config,
                             "repetition": repetition, "block": index + 1,
                             "position": position,
                             "estimated_admission_allowance_usd": _usd(allowance)})
    normalized = {**spec, "tasks": [tasks[t] for t in sorted(tasks)],
                  "configurations": [configs[c] for c in sorted(configs)],
                  "allowance_per_trial_usd": _usd(allowance),
                  "max_total_usd": _usd(ceiling)}
    result = {"schema_version": 1, "scope": "prospective_operator_declared_design",
              "status": "plan_only", "spec": normalized, "repetitions": REPETITIONS,
              "planned_trial_count": count, "estimated_admission_total_usd": _usd(total),
              "paid_execution_authorized": False, "provider_hard_cap_verified": False,
              "commitments_independently_verified": False,
              "trials": schedule}
    result["plan_sha256"] = digest(result)
    return result


def validate_plan(plan: dict) -> None:
    """Reconstruct support, sequence, cost bounds and digest; reject edits."""
    if (not isinstance(plan, dict)
            or plan.get("plan_sha256") != digest({k: v for k, v in plan.items()
                                                  if k != "plan_sha256"})
            or plan != build_plan(plan.get("spec"))):
        raise ReceiptError("plan does not match its prospective design")


def read_json(path: Path) -> dict:
    """Read a bounded local file and reject duplicate keys."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ReceiptError("unsafe or oversized design file")
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ReceiptError("duplicate design field")
            out[k] = v
        return out
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = build_plan(read_json(args.spec))
        validate_plan(plan)
        publish_private_texts([(args.output, json.dumps(plan, indent=2, sort_keys=True) + "\n")])
    except (ReceiptError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
