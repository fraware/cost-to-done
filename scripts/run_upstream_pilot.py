"""Prepare and optionally execute a matched public upstream development panel.

The paid route is restricted to the dedicated manually dispatched main
workflow. No arbitrary repositories, provider invoice claims, or holdout
claims. One unresolved episode stops further spending; every planned
episode remains visible in the summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import PriceSchedule
from cost_to_done.ledger import _units, _usd
from cost_to_done.live import LiveConfig, plan_live, prepare_task, execute_live
from cost_to_done.private_files import publish_private_texts
from cost_to_done.repository_comparison import digest, is_digest
from cost_to_done.repository_qualification import check_qualification
from cost_to_done.upstream_pilot import (
    ALLOWANCE, MODELS, REPETITIONS, STARTERS, trusted_upstream_dispatch,
    validate_upstream_starter,
)
from scripts.run_real_model_smoke import attestation
from scripts.run_repository_pilot import complete_record

SCOPE = "fixed_public_upstream_development_panel"
SEED = 20261125


def write(path: Path, record: dict) -> None:
    publish_private_texts([(path, json.dumps(record, sort_keys=True, indent=2,
                                            allow_nan=False) + "\n")])


def build_plan(tasks: dict, schedules: dict, harness_commit: str) -> dict:
    if (not isinstance(tasks, dict) or set(tasks) != set(STARTERS)
            or not all(is_digest(x) for x in tasks.values())
            or len(set(tasks.values())) != len(tasks)
            or not isinstance(schedules, dict) or set(schedules) != set(MODELS)
            or not all(is_digest(x) for x in schedules.values())
            or not isinstance(harness_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", harness_commit)):
        raise ReceiptError("invalid upstream panel commitments")
    blocks = [(name, rep) for name in STARTERS for rep in range(1, REPETITIONS + 1)]
    blocks.sort(key=lambda b: digest([SEED, b]))
    models = sorted(MODELS)
    trials = []
    for block, (task, rep) in enumerate(blocks):
        order = models if block % 2 == 0 else models[::-1]
        for model in order:
            trials.append({"id": f"{task}:{model}:r{rep}", "task": task,
                           "model": model, "repetition": rep,
                           "allowance_usd": ALLOWANCE})
    plan = {
        "schema_version": 1, "scope": SCOPE, "harness_commit": harness_commit,
        "seed": SEED, "starter_pins": STARTERS.copy(),
        "qualification_digests": tasks.copy(), "price_schedule_digests": schedules.copy(),
        "api": "responses", "reasoning_effort": "low", "max_turns": 5,
        "max_wall_seconds": 900, "attempts_per_trial": 1,
        "provider_hard_cap_verified": False, "provider_invoice_reconciled": False,
        "held_out": False, "planned_trials": len(trials),
        "aggregate_admission_allowance_usd": _usd(len(trials) * _units(ALLOWANCE)),
        "trials": trials,
    }
    plan["plan_sha256"] = digest(plan)
    return plan


def validate_plan(plan: dict) -> None:
    if (not isinstance(plan, dict) or plan != build_plan(
            plan.get("qualification_digests"), plan.get("price_schedule_digests"),
            plan.get("harness_commit"))):
        raise ReceiptError("upstream panel plan changed")


def trial_complete(plan: dict, trial: dict, record: dict) -> bool:
    if (record.get("trial_id") != trial["id"] or record.get("scope") != SCOPE
            or record.get("model") != trial["model"]
            or record.get("qualification_sha256") != plan["qualification_digests"][trial["task"]]
            or record.get("repository_execution_scope") != "fixed_public_upstream_pilot"):
        return False
    subplan = {"plan_sha256": plan["plan_sha256"],
               "task_input_sha256": STARTERS[trial["task"]],
               "models": [{"model": trial["model"],
                           "price_schedule_sha256": plan["price_schedule_digests"][trial["model"]]}]}
    return complete_record(record, subplan)


def summarize(plan: dict, records: list[dict]) -> dict:
    validate_plan(plan)
    if (not isinstance(records, list) or len(records) > len(plan["trials"])
            or any(not isinstance(r, dict) for r in records)):
        raise ReceiptError("invalid observation list")
    hashes = set()
    task_checksums = defaultdict(set)
    rows = []
    known = defaultdict(list)
    for idx, trial in enumerate(plan["trials"]):
        record = records[idx] if idx < len(records) else None
        state, cost = "missing", None
        if record is not None:
            if (record.get("trial_id") != trial["id"]
                    or record.get("plan_sha256") != plan["plan_sha256"]
                    or record.get("model") != trial["model"]
                    or record.get("task_input_sha256") != STARTERS[trial["task"]]
                    or record.get("scope") != SCOPE):
                raise ReceiptError("observation does not match prospective order and identity")
            cost = record.get("gateway_rate_card_estimate_usd")
            if cost is not None:
                known[trial["model"]].append(_units(cost))
            state = "unresolved"
            if trial_complete(plan, trial, record):
                raw = record["harbor_raw_result_sha256"]
                if raw in hashes:
                    raise ReceiptError("duplicate raw Harbor result hash")
                hashes.add(raw)
                task_checksums[trial["task"]].add(record["harbor_task_checksum"])
                state = record["harbor_trial_outcome"]
        rows.append({**trial, "outcome": state, "known_estimate_usd": cost})
    complete = (all(r["outcome"] in ("pass", "fail") for r in rows)
                and set(task_checksums) == set(STARTERS)
                and all(len(x) == 1 for x in task_checksums.values()))
    configurations = []
    for model in sorted(MODELS):
        selected = [r for r in rows if r["model"] == model]
        passes = sum(r["outcome"] == "pass" for r in selected)
        total = sum(known[model])
        configurations.append({
            "model": model, "planned": len(selected), "passes": passes,
            "failures": sum(r["outcome"] == "fail" for r in selected),
            "missing": sum(r["outcome"] == "missing" for r in selected),
            "unresolved": sum(r["outcome"] == "unresolved" for r in selected),
            "known_cost_records": len(known[model]),
            "known_estimate_usd": _usd(total) if known[model] else None,
            # Retain the exact numerator and denominator; no rounding to an
            # integer picodollar or division by zero.
            "cost_per_completion": {"numerator_usd": _usd(total),
                                    "denominator": passes} if complete and passes else None,
        })
    return {"scope": SCOPE, "plan_sha256": plan["plan_sha256"],
            "complete_matched_accounting": complete, "held_out": False,
            "eligible_for_ranking": False, "provider_invoice_reconciled": False,
            "independent_replay": False, "configurations": configurations, "trials": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("controls", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute and not trusted_upstream_dispatch():
        parser.error("trusted manual upstream dispatch required")
    root, controls, output = (p.resolve() for p in (args.root, args.controls, args.output))
    tasks = {}
    for name in STARTERS:
        task = controls / name / "starter"
        validate_upstream_starter(task)
        receipt = check_qualification(task, controls / name / "qualification.json", STARTERS[name])
        tasks[name] = receipt["qualification_sha256"]
    schedules = {}
    for model, relative in MODELS.items():
        price = PriceSchedule.load(root / relative)
        if price.model != model:
            raise ReceiptError("price schedule identity mismatch")
        schedules[model] = price.digest
    plan = build_plan(tasks, schedules, os.environ.get("GITHUB_SHA", ""))
    output.mkdir(mode=0o700, exist_ok=False)
    write(output / "plan.json", plan)
    records = []
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as directory:
        private = Path(directory)
        key = private / "upstream.key"
        def config(trial):
            name, model = trial["task"], trial["model"]
            # Distinct job names, stable but never passed through a shell.
            job = "up-" + hashlib.sha256(trial["id"].encode()).hexdigest()[:24]
            return LiveConfig(root, controls / name / "starter", private / "jobs",
                              model, root / MODELS[model], key, ALLOWANCE,
                              job, 5, 900, "responses", "low",
                              repository_task_sha256=STARTERS[name],
                              repository_qualification=controls / name / "qualification.json",
                              repository_upstream_pilot=True)
        # Stage every task/configuration pair before reading any paid credential.
        # This tests the actual Pi packaging and external route, not model output.
        for index, trial in enumerate(plan["trials"]):
            c = config(trial)
            preview = plan_live(c)
            if preview["repository_execution_scope"] != "fixed_public_upstream_pilot":
                raise ReceiptError("wrong execution scope")
            prepare_task(c.validated(), private / f"stage-{index:02d}")
        if not args.execute:
            write(output / "preflight.json", {"scope": SCOPE, "plan_sha256": plan["plan_sha256"],
                  "staged_trials": len(plan["trials"]), "provider_calls": 0,
                  "paid_execution_authorized": False})
            return 0
        credential = os.environ.pop("CTD_OPENAI_SECRET", "")
        if not credential:
            raise ReceiptError("provider credential unavailable")
        fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(credential)
        del credential
        for index, trial in enumerate(plan["trials"]):
            name, model = trial["task"], trial["model"]
            c = config(trial)
            write(output / f"{index:02d}.intent.json",
                  {"trial_id": trial["id"], "plan_sha256": plan["plan_sha256"],
                   "status": "attempt_intended"})
            try:
                outcome = execute_live(c, acknowledged=True)
            except (ReceiptError, OSError, ValueError, RuntimeError):
                outcome = {"status": "incomplete_or_uncertain",
                           "api": "responses", "reasoning_effort": "low"}
            record = attestation(outcome, model)
            record.update(trial_id=trial["id"], plan_sha256=plan["plan_sha256"],
                          task_input_sha256=STARTERS[name], scope=SCOPE,
                          qualification_sha256=tasks[name], mock_only=False,
                          repository_execution_scope=outcome.get("repository_execution_scope"))
            write(output / f"{index:02d}.json", record)
            records.append(record)
            if not trial_complete(plan, trial, record):
                break
            # Stop on any repeated result hash or differing task checksum.
            if len({r["harbor_raw_result_sha256"] for r in records}) != len(records):
                break
            if len({r["harbor_task_checksum"] for r in records
                    if r["task_input_sha256"] == STARTERS[name]}) != 1:
                break
    report = summarize(plan, records)
    write(output / "summary.json", report)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if report["complete_matched_accounting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
