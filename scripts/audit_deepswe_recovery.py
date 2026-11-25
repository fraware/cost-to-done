"""Audit reported DeepSWE assignment outcomes and recovery accounting.

Reads one public publisher's JSON export as data, never executes its code.
This is a source-specific descriptive audit; cost records are aggregated
by the publisher. No per-task cost, invoice or independent execution claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal, localcontext
from pathlib import Path

SOURCE = "https://reasonmachines.com/research/reason-agent-deepswe/deepswe.json"
REVISION = "0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea"
UPDATED = "2026-09-14T07:05:00.816208Z"
SOURCE_SHA256 = "8128f434c608473a8987bc9d5e02ff578fcac4d6f7c611e8f4436740330f355c"
RUNS = {"reason-astra-1": ("Reason", 1), "reason-astra-2": ("Reason", 2),
        "codex-astra-1": ("Codex", 1)}
OUTCOMES = {"pass", "fail", "ungraded"}
MAX_BYTES = 2_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, "duplicate JSON key")
        out[k] = v
    return out


def invalid_constant(value):
    raise ValueError("invalid numeric constant: " + value)


def nonnegative(value):
    require(type(value) in (Decimal, int), "invalid numeric type")
    number = Decimal(value)
    require(number.is_finite() and 0 <= number <= Decimal("1000000000"),
            "invalid numeric amount")
    return number


def audit(raw: bytes) -> dict:
    require(0 < len(raw) <= MAX_BYTES, "invalid source length")
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "source byte digest mismatch")
    doc = json.loads(raw, parse_float=Decimal, parse_constant=invalid_constant,
                     object_pairs_hook=unique)
    require(doc["schema_version"] == "1.1.0" and doc["updated_at"] == UPDATED,
            "unexpected publisher snapshot")
    bench = doc["benchmark"]
    require((bench["name"], bench["version"], bench["tasks"], bench["dataset_revision"])
            == ("DeepSWE", "1.1", 113, REVISION), "unexpected benchmark identity")
    require(type(doc["runs"]) is list and len(doc["runs"]) == len(RUNS),
            "unexpected run count")
    seen, support = set(), None
    final = {"Reason": Counter(), "Codex": Counter()}
    original = {"Reason": Counter(), "Codex": Counter()}
    recovery = {"Reason": Counter(), "Codex": Counter()}
    for run in doc["runs"]:
        name = run["id"]
        require(name in RUNS and name not in seen, "unexpected or repeated run")
        seen.add(name)
        agent, repetition = RUNS[name]
        require((run["agent"], run["repetition"], run["model"], run["effort"])
                == (agent, repetition, "gpt-6-astra", "xhigh"),
                "configuration mismatch")
        tasks = run["tasks"]
        require(type(tasks) is dict and len(tasks) == 113, "incomplete assignments")
        if support is None:
            support = set(tasks)
        require(set(tasks) == support, "task-name support differs")
        counts = Counter()
        for task, row in tasks.items():
            require(isinstance(task, str) and task and len(task) <= 250, "invalid task ID")
            verdict = row["outcome"]
            require(verdict in OUTCOMES, "invalid outcome")
            counts[verdict] += 1
            final[agent][verdict] += 1
            previous = verdict
            if "recovery" in row:
                rec = row["recovery"]
                kind = rec["kind"]
                require(isinstance(kind, str) and 0 < len(kind) <= 100,
                        "invalid recovery identity")
                previous = rec["original"]["outcome"]
                require(previous in OUTCOMES, "invalid original recovery outcome")
                recovery[agent][kind] += 1
            original[agent][previous] += 1
        expected = {"assigned": 113, "passed": counts["pass"],
                    "failed": counts["fail"], "ungraded": counts["ungraded"]}
        require(all(type(run["summary"][k]) is int and run["summary"][k] == v
                    for k, v in expected.items()), "run summary disagrees with task records")
    aggregates = doc["aggregates"]
    require(type(aggregates) is list and len(aggregates) == 2, "unexpected aggregates")
    aggregate_agents = set()
    for row in aggregates:
        agent = row["agent"]
        require(agent in final and agent not in aggregate_agents, "invalid aggregate identity")
        aggregate_agents.add(agent)
        counts = final[agent]
        expected = {"assigned": sum(counts.values()), "passed": counts["pass"],
                    "failed": counts["fail"], "ungraded": counts["ungraded"]}
        require(all(type(row[k]) is int and row[k] == v for k, v in expected.items()),
                "aggregate differs from task outcomes")
        require(set(row["run_ids"]) == {k for k, v in RUNS.items() if v[0] == agent},
                "aggregate run identity mismatch")

    # These assertions specify the exact historical snapshot and prevent
    # changed recovery semantics from silently passing the current audit.
    require(final["Reason"] == Counter({"pass": 165, "fail": 61})
            and original["Reason"] == Counter({"pass": 164, "fail": 60, "ungraded": 2})
            and recovery["Reason"] == Counter({"fresh_attempt_after_setup_failure": 1,
                                               "unchanged_patch_regrade": 1}),
            "unexpected Reason recovery history")
    cost = doc["cost_score"]["reason_astra"]
    expected = {"assigned_attempts": sum(final["Reason"].values()),
                "confirmed_passes": final["Reason"]["pass"],
                "ungraded_attempts": final["Reason"]["ungraded"]}
    require(all(type(cost[k]) is int and cost[k] == v for k, v in expected.items()),
            "cost support disagrees with assignment outcomes")
    known, missing = cost["cost_records"], cost["missing_cost_records"]
    require(type(known) is int and type(missing) is int and known >= 0 and missing >= 0
            and known + missing == expected["assigned_attempts"], "invalid cost coverage")
    spend = nonnegative(cost["recorded_model_spend_usd"])
    recovery_spend = nonnegative(cost["recovery_model_spend_usd"])
    require(recovery_spend <= spend, "recovery spend exceeds total")
    mean = nonnegative(cost["mean_recorded_cost_per_assigned_attempt_usd"])
    with localcontext() as context:
        context.prec = 40
        require(abs(mean - spend / expected["assigned_attempts"]) <= Decimal("0.000000000001"),
                "mean cost disagrees with reported aggregate")
    # The publisher says recovery spend is included, not additive. The
    # publisher also reports no inference on the setup failure and regrade.
    # These statements are not established by the task outcome records.
    rows = []
    for agent in ("Reason", "Codex"):
        counts = final[agent]
        rows.append({"agent": agent, "assigned_slots": sum(counts.values()),
                     "original_outcomes": {k: original[agent][k] for k in sorted(OUTCOMES)},
                     "final_outcomes": {k: counts[k] for k in sorted(OUTCOMES)},
                     "reported_recovery_kinds": dict(sorted(recovery[agent].items())),
                     "reported_cost_records": known if agent == "Reason" else None,
                     "reported_missing_cost_records": missing if agent == "Reason" else None,
                     "recorded_model_spend_usd": str(spend) if agent == "Reason" else None,
                     "reported_cost_per_final_pass": {
                         "numerator_usd": str(spend), "denominator": counts["pass"]}
                     if agent == "Reason" and missing == 0 and counts["pass"] > 0 else None})
    return {"schema_version": 1, "scope": "external_publisher_outcomes_and_aggregate_cost",
            "source_url": SOURCE, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_updated_at": UPDATED, "dataset_revision": REVISION,
            "matched_task_names": len(support), "assignment_records": sum(
                sum(c.values()) for c in final.values()),
            "reason_reported_physical_attempts": 227,
            "reason_reported_recovery_spend_included_usd": str(recovery_spend),
            "cost_coverage_independently_verified": False, "provider_invoice_reconciled": False,
            "task_digest_support_verified": False, "comparative_cost_ratio_available": False,
            "eligible_for_ranking": False, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.source.open("rb") as stream:
        report = audit(stream.read(MAX_BYTES + 1))
    payload = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8") as output:
        output.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
