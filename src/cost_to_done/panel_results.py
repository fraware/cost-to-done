"""Conservative planned-trial accounting for the public development panel."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .ledger import _units, _usd
from .panel import _canonical, _sha, CONFIGURATIONS
from .live import TRUSTED_TASK_MODULES

COMPLETE = "completed_with_unverified_rate_card_estimate"


def _digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_plan(plan: dict) -> None:
    """Check prospective matched support independently of the self-declared hash.

    Historical manifests need not match the current checkout; this validates
    structure, not the authenticity of the original experimental execution.
    """
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ReceiptError("unsupported panel plan")
    if plan.get("plan_sha256") != _sha(_canonical({k: v for k, v in plan.items()
                                                  if k != "plan_sha256"})):
        raise ReceiptError("panel plan digest mismatch")
    repetitions = plan.get("repetitions")
    tasks = plan.get("tasks")
    configs = plan.get("configurations")
    trials = plan.get("trials")
    if (plan.get("scope") != "public_development_fixtures"
            or plan.get("status") != "plan_only"
            or type(repetitions) is not int or not 1 <= repetitions <= 10
            or not isinstance(tasks, dict) or set(tasks) != set(TRUSTED_TASK_MODULES)
            or not isinstance(configs, dict) or set(configs) != set(CONFIGURATIONS)
            or not isinstance(trials, list)
            or plan.get("provider_hard_cap_verified") is not False
            or plan.get("paid_execution_authorized") is not False):
        raise ReceiptError("invalid bundled panel definition")
    for name, configuration in configs.items():
        model, price_path = CONFIGURATIONS[name]
        if (not isinstance(configuration, dict) or configuration.get("model") != model
                or configuration.get("price_schedule") != price_path
                or not _digest(configuration.get("price_schedule_sha256"))
                or configuration.get("api") != "responses"
                or configuration.get("reasoning_effort") != "low"):
            raise ReceiptError("invalid panel configuration")
    required = {(task, config, rep) for task in tasks for config in configs
                for rep in range(1, repetitions + 1)}
    actual = set()
    allowance_units = 0
    for trial in trials:
        if not isinstance(trial, dict):
            raise ReceiptError("invalid planned episode")
        task, config, rep = (trial.get(k) for k in ("task", "configuration", "repetition"))
        if (not isinstance(task, str) or not isinstance(config, str)
                or type(rep) is not int or (task, config, rep) not in required
                or (task, config, rep) in actual
                or trial.get("trial_id") != f"panel-{task}-{config}-r{rep:02d}"):
            raise ReceiptError("invalid or duplicate planned task/configuration/repetition")
        actual.add((task, config, rep))
        allowance_units += _units(trial.get("estimated_admission_allowance_usd"), allow_zero=False)
    if (actual != required or type(plan.get("planned_trial_count")) is not int
            or plan["planned_trial_count"] != len(required)
            or allowance_units != _units(plan.get("estimated_admission_total_usd"))
            or allowance_units > _units(plan.get("declared_ceiling_usd"), allow_zero=False)):
        raise ReceiptError("unmatched planned support or invalid aggregate allowance")


def summarize_panel(plan: dict, records: list[dict]) -> dict:
    """Account for every planned episode; never impute unknown spend as zero.

    Ratios are descriptive only, and withheld globally if any task support,
    verifier outcome, monetary liability, or task identity is unresolved.
    """
    validate_plan(plan)
    trials = plan["trials"]
    expected = {x["trial_id"]: x for x in trials}
    if len(expected) != len(trials) or len(trials) != plan["planned_trial_count"]:
        raise ReceiptError("invalid panel trial support")
    seen = {}
    raw_hashes = set()
    for record in records:
        if not isinstance(record, dict):
            raise ReceiptError("panel observation must be an object")
        tid = record.get("trial_id")
        if not isinstance(tid, str) or tid not in expected or tid in seen:
            raise ReceiptError("unexpected or duplicate panel trial")
        trial = expected[tid]
        config = plan["configurations"][trial["configuration"]]
        if (record.get("plan_sha256") != plan["plan_sha256"]
                or record.get("model") != config["model"]
                or record.get("task_fixture") != trial["task"]
                or record.get("api") != config["api"]
                or record.get("reasoning_effort") != config["reasoning_effort"]
                or record.get("price_schedule_sha256") != config["price_schedule_sha256"]
                or record.get("provider_invoice_reconciled") is not False
                or record.get("provider_spend_limit_verified") is not False
                or record.get("verifier_independently_reexecuted") is not False):
            raise ReceiptError("panel observation identity or disclosure mismatch")
        raw_hash = record.get("harbor_raw_result_sha256")
        if raw_hash is not None:
            if not _digest(raw_hash) or raw_hash in raw_hashes:
                raise ReceiptError("invalid or repeated raw Harbor result identity")
            raw_hashes.add(raw_hash)
        seen[tid] = record

    rows = {name: {"configuration": name, "planned": 0, "observed": 0,
                   "passed": 0, "failed": 0, "unresolved": 0,
                   "missing": 0, "known_cost_records": 0, "known_units": 0}
            for name in plan["configurations"]}
    checksums: dict[str, set[str]] = {}
    details = []
    for trial in trials:
        tid = trial["trial_id"]
        row = rows[trial["configuration"]]
        row["planned"] += 1
        rec = seen.get(tid)
        if rec is None:
            row["missing"] += 1
            details.append({"trial_id": tid, "state": "missing"})
            continue
        row["observed"] += 1
        cost = rec.get("gateway_rate_card_estimate_usd")
        known = None
        if cost is not None:
            if rec.get("ledger_observed") is not True:
                raise ReceiptError("cost present without observed ledger")
            known = _units(cost)
            row["known_cost_records"] += 1
            row["known_units"] += known
        outcome = rec.get("harbor_trial_outcome")
        checksum = rec.get("harbor_task_checksum")
        settled = (rec.get("trial_status") == COMPLETE
                   and rec.get("ledger_observed") is True
                   and type(rec.get("gateway_pending")) is int and rec["gateway_pending"] == 0
                   and type(rec.get("gateway_uncertain")) is int and rec["gateway_uncertain"] == 0
                   and rec.get("gateway_breached") is False
                   and type(rec.get("gateway_recorded_calls")) is int and rec["gateway_recorded_calls"] > 0
                   and known is not None and known <= _units(trial["estimated_admission_allowance_usd"])
                   and _digest(checksum) and _digest(rec.get("harbor_raw_result_sha256"))
                   and outcome in ("pass", "fail"))
        if settled:
            checksums.setdefault(trial["task"], set()).add(checksum)
            row["passed" if outcome == "pass" else "failed"] += 1
            state = outcome
        else:
            row["unresolved"] += 1
            state = "unresolved"
        details.append({"trial_id": tid, "state": state,
                        "known_rate_card_estimate_usd": _usd(known) if known is not None else None})
    matched = all(len(values) == 1 for values in checksums.values())
    complete = (matched and len(checksums) == len(plan["tasks"])
                and all(not (r["missing"] or r["unresolved"]) for r in rows.values()))
    from decimal import Decimal
    result = []
    for row in rows.values():
        units = row.pop("known_units")
        row["known_rate_card_estimate_usd"] = _usd(units) if row["known_cost_records"] else None
        row["cost_per_verified_completion_usd"] = (
            format(Decimal(units) / Decimal(10**12) / row["passed"], "f")
            if complete and row["passed"] else None)
        result.append(row)
    return {"schema_version": 1, "plan_sha256": plan["plan_sha256"],
            "scope": "public_development_fixtures_descriptive_only",
            "complete_matched_accounting": complete, "eligible_for_ranking": False,
            "task_checksums_consistent": matched, "provider_invoice_reconciled": False,
            "verifier_independently_reexecuted": False, "rows": result, "trials": details}

def read_panel_directory(directory: Path) -> tuple[dict, list[dict]]:
    """Read bounded JSON evidence files; ignore only the derived summary."""
    import json

    if directory.is_symlink() or not directory.is_dir():
        raise ReceiptError("panel directory must be a real directory")
    root = directory.resolve(strict=True)

    def read(path: Path) -> dict:
        if (path.is_symlink() or not path.is_file() or path.resolve() != path
                or path.stat().st_size > 2_000_000):
            raise ReceiptError("unsafe or oversized panel evidence")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ReceiptError("panel evidence must be a JSON object")
        return obj

    plan = read(root / "plan.json")
    observations = []
    for path in sorted(root.glob("*.json")):
        if path.name in ("plan.json", "summary.json"):
            continue
        record = read(path)
        if record.get("trial_id") != path.stem:
            raise ReceiptError("panel observation filename identity mismatch")
        observations.append(record)
    return plan, observations
