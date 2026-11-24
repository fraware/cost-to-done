"""Explicit trusted-main, serial, two-model pilot on the fixed public fixture."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from cost_to_done.gateway import PriceSchedule
from cost_to_done.ledger import _units, _usd
from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.private_files import publish_private_texts
from cost_to_done.repository_pilot import MODELS, trusted_dispatch, validate_fixed_starter
from cost_to_done.repository_qualification import check_qualification
from cost_to_done.repository_comparison import digest, is_digest
from scripts.run_real_model_smoke import attestation


def write(path: Path, record: dict) -> None:
    publish_private_texts([(path, json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n")])


def main() -> int:
    if len(sys.argv) != 5 or not trusted_dispatch():
        raise SystemExit("trusted manual pilot authorization missing")
    root, task, qualification, output = (Path(x).resolve() for x in sys.argv[1:])
    starter = validate_fixed_starter(task)
    pinned = starter["task_input_sha256"]
    qual = check_qualification(task, qualification, pinned)
    output.mkdir(mode=0o700, exist_ok=False)
    plan = {"schema_version": 1, "scope": "fixed_public_synthetic_external_repository",
            "task_input_sha256": pinned, "qualification_sha256": qual["qualification_sha256"],
            "api": "responses", "reasoning_effort": "low", "max_turns": 5,
            "max_wall_seconds": 900, "allowance_per_trial_usd": "1",
            "aggregate_admission_allowance_usd": "2", "provider_hard_cap_verified": False,
            "models": [{"model": model, "price_schedule_sha256": PriceSchedule.load(root / schedule).digest}
                       for model, schedule in MODELS.items()]}
    plan["plan_sha256"] = digest(plan)
    write(output / "plan.json", plan)
    credential = os.environ.pop("CTD_OPENAI_SECRET", "")
    if not credential:
        raise SystemExit("provider credential unavailable")
    records = []
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as directory:
        key = Path(directory) / "upstream.key"
        fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(credential)
        del credential
        for model, schedule in MODELS.items():
            write(output / (model + ".intent.json"), {"model": model, "plan_sha256": plan["plan_sha256"],
                                                      "status": "attempt_intended"})
            config = LiveConfig(root, task, Path(directory) / "jobs", model,
                                root / schedule, key, "1", "pilot-" + model.replace(".", "-"),
                                5, 900, "responses", "low", repository_task_sha256=pinned,
                                repository_qualification=qualification, repository_pilot=True)
            try:
                outcome = execute_live(config, acknowledged=True)
            except (OSError, ValueError, RuntimeError):
                outcome = {"status": "incomplete_or_uncertain", "api": "responses",
                           "reasoning_effort": "low", "task_fixture": task.name}
            record = attestation(outcome, model)
            record.update(plan_sha256=plan["plan_sha256"], task_input_sha256=pinned,
                          scope=plan["scope"], mock_only=False)
            write(output / (model + ".json"), record)
            print(json.dumps(record, sort_keys=True, allow_nan=False), flush=True)
            records.append(record)
            if not complete_record(record, plan):
                break
            if len(records) == 2 and records[0]["harbor_task_checksum"] != records[1]["harbor_task_checksum"]:
                break
    summary = summarize(plan, records)
    write(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, allow_nan=False))
    return 0 if summary["complete_matched_accounting"] else 2


def complete_record(record: dict, plan: dict) -> bool:
    schedules = {x["model"]: x["price_schedule_sha256"] for x in plan["models"]}
    cost = record.get("gateway_rate_card_estimate_usd")
    return (record.get("model") in schedules and record.get("plan_sha256") == plan["plan_sha256"]
            and record.get("task_input_sha256") == plan["task_input_sha256"]
            and record.get("price_schedule_sha256") == schedules[record["model"]]
            and record.get("trial_status") == "completed_with_unverified_rate_card_estimate"
            and record.get("api") == "responses" and record.get("reasoning_effort") == "low"
            and record.get("mock_only") is False and record.get("ledger_observed") is True
            and record.get("provider_invoice_reconciled") is False
            and record.get("provider_spend_limit_verified") is False
            and record.get("verifier_independently_reexecuted") is False
            and record.get("harbor_trial_outcome") in ("pass", "fail")
            and type(record.get("gateway_pending")) is int and record["gateway_pending"] == 0
            and type(record.get("gateway_uncertain")) is int and record["gateway_uncertain"] == 0
            and record.get("gateway_breached") is False
            and type(record.get("gateway_recorded_calls")) is int and record["gateway_recorded_calls"] > 0
            and cost is not None and 0 < _units(cost) <= _units("1")
            and is_digest(record.get("harbor_task_checksum"))
            and is_digest(record.get("harbor_raw_result_sha256")))


def summarize(plan: dict, records: list[dict]) -> dict:
    expected = [x["model"] for x in plan["models"]]
    if [x["model"] for x in records] != expected[:len(records)]:
        raise ValueError("observations do not match the declared serial plan")
    complete = (len(records) == len(expected) and all(complete_record(r, plan) for r in records)
                and len({r["harbor_task_checksum"] for r in records}) == 1
                and len({r["harbor_raw_result_sha256"] for r in records}) == len(records))
    observed = {x["model"]: x for x in records}
    rows = []
    known = []
    for model in expected:
        r = observed.get(model, {})
        cost = r.get("gateway_rate_card_estimate_usd")
        if cost is not None:
            known.append(_units(cost))
        outcome = r.get("harbor_trial_outcome")
        rows.append({"model": model, "outcome": outcome if complete_record(r, plan) else
                     "unresolved" if r else "missing", "known_estimate_usd": cost,
                     "cost_per_completion_usd": cost if complete and outcome == "pass" else None})
    return {"scope": plan["scope"], "plan_sha256": plan["plan_sha256"],
            "complete_matched_accounting": complete, "eligible_for_ranking": False,
            "provider_invoice_reconciled": False, "independent_replay": False,
            "known_total_estimate_usd": _usd(sum(known)) if known else None, "rows": rows}


if __name__ == "__main__":
    raise SystemExit(main())
