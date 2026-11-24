"""Recompute descriptive inference-cost ratios from a pinned upstream snapshot.

Reads committed JSON blobs, never executes upstream code, never calls a model.
The input is aggregate submission metadata, not raw trial receipts. In
particular upstream sums missing trial cost as zero, so completeness is unknown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

UPSTREAM = "https://github.com/harbor-framework/terminal-bench"
REVISION = "ad4c7aae7b6f1fd80e514dc85768e46d02661bef"
TARGET = "4-1-0"
DIRECTORY = "leaderboard/submissions"
MAX_FILES = 500
MAX_BYTES = 2_000_000


def reject_constant(value: str):
    raise ValueError("Nonfinite JSON number: " + value)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("Oversized upstream submission")
    value = json.loads(raw, parse_float=Decimal, parse_constant=reject_constant,
                       object_pairs_hook=unique_pairs)
    if not isinstance(value, dict):
        raise ValueError("Upstream submission must be an object")
    return value


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "--no-replace-objects", "-C", str(root),
                                    *args], timeout=30)


def iter_submissions(root: Path):
    """Read the immutable Git tree, excluding uncommitted working-tree data."""
    commit = git(root, "rev-parse", REVISION + "^{commit}").decode().strip()
    if commit != REVISION:
        raise ValueError("Unexpected upstream commit")
    entries = git(root, "ls-tree", "-r", "-z", REVISION, "--", DIRECTORY).split(b"\0")
    selected = []
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        name = path.decode("utf-8")
        if not name.endswith(".json"):
            continue
        if (mode not in ("100644", "100755") or kind != "blob"
                or not re.fullmatch(r"leaderboard/submissions/[A-Za-z0-9._-]+\.json", name)):
            raise ValueError("Unexpected upstream submission path or mode")
        selected.append((name, blob))
    if not 0 < len(selected) <= MAX_FILES:
        raise ValueError("Unexpected submission count")
    for name, blob in sorted(selected):
        size = int(git(root, "cat-file", "-s", blob))
        if not 0 < size <= MAX_BYTES:
            raise ValueError("Unexpected upstream blob size")
        raw = git(root, "cat-file", "blob", blob)
        if len(raw) != size:
            raise ValueError("Upstream blob size changed")
        yield name, blob, raw


def count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def money(value: Any) -> Decimal | None:
    if type(value) not in (Decimal, int, str):
        return None
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    if not result.is_finite() or not 0 <= result <= Decimal("1000000000"):
        return None
    if result.as_tuple().exponent < -8:
        return None
    return result


def ratio(cost: Decimal | None, successes: int | None, trials: int | None) -> str | None:
    if (cost is None or cost <= 0 or successes is None or not successes
            or trials is None or successes > trials):
        return None
    with localcontext() as context:
        context.prec = 40
        return format((cost / successes).quantize(Decimal("0.000001")), "f")


def text_field(value: Any) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 250 else None


def extract(name: str, blob: str, raw: bytes) -> dict | None:
    doc = read_json(raw)
    # Upstream documents that records with no explicit target default to 4.0.
    if doc.get("leaderboard") != TARGET:
        return None
    metrics = doc.get("metrics")
    source = doc.get("source_filter")
    meta = doc.get("metadata")
    metrics = metrics if isinstance(metrics, dict) else {}
    source = source if isinstance(source, dict) else {}
    meta = meta if isinstance(meta, dict) else {}
    n = count(metrics.get("n_trials"))
    s = count(metrics.get("successes"))
    cost = money(metrics.get("total_cost_usd"))
    ids = doc.get("trials")
    ids_count = len(ids) if isinstance(ids, list) else None
    ids_unique = (len(set(ids)) == len(ids) if isinstance(ids, list)
                  and all(isinstance(x, str) for x in ids) else None)
    jobs = doc.get("source_jobs")
    job_ids = [x for x in jobs if text_field(x)] if isinstance(jobs, list) else []
    state = "reported_aggregate_only"
    if n is None or s is None or s > n or not n or cost is None:
        state = "incomplete_or_invalid_aggregate"
    elif cost == 0:
        state = "zero_reported_cost_unverified"
    elif not s:
        state = "zero_successes"
    elif ids_unique is False or (ids_count is not None and ids_count != n):
        state = "trial_identifier_mismatch"
    reported_ratio = ratio(cost, s, n) if state == "reported_aggregate_only" else None
    return {
        "source_path": name,
        "source_blob": blob,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_jobs": job_ids,
        "model": text_field(source.get("model_name")),
        "agent": text_field(source.get("agent")),
        "agent_version": text_field(source.get("agent_version")),
        "reasoning_effort": text_field(source.get("reasoning_effort")),
        "release_date": text_field(meta.get("date")),
        "n_trials": n,
        "reported_successes": s,
        "reported_inference_cost_usd": format(cost, "f") if cost is not None else None,
        "reported_inference_cost_per_success_usd": reported_ratio,
        "trial_id_count": ids_count,
        "trial_ids_unique": ids_unique,
        "state": state,
        "trial_cost_completeness_verified": False,
    }


def snapshot(root: Path) -> dict:
    rows = []
    scanned = 0
    for name, blob, raw in iter_submissions(root):
        scanned += 1
        row = extract(name, blob, raw)
        if row is not None:
            rows.append(row)
    if not rows:
        raise ValueError("No explicit Terminal-Bench 4.1 submissions found")
    rows.sort(key=lambda r: (r["model"] or "", r["agent"] or "",
                             r["reasoning_effort"] or "", r["source_path"]))
    return {
        "schema_version": 1,
        "source_repository": UPSTREAM,
        "source_commit": REVISION,
        "leaderboard": TARGET,
        "source_records_scanned": scanned,
        "target_records": len(rows),
        "non_target_records": scanned - len(rows),
        "ratios_available": sum(r["reported_inference_cost_per_success_usd"] is not None for r in rows),
        "scope": "external_committed_submission_aggregates",
        "raw_trial_costs_reconciled": False,
        "invoice_reconciled": False,
        "paired_task_support_verified": False,
        "eligible_for_ranking": False,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = snapshot(args.upstream_checkout.resolve(strict=True))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    # Compact derived facts only. Source JSON and trajectories are not uploaded.
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, sort_keys=True))
    for row in report["rows"]:
        print(json.dumps({k: row[k] for k in (
            "model", "agent", "reasoning_effort", "n_trials", "reported_successes",
            "reported_inference_cost_usd", "reported_inference_cost_per_success_usd", "state",
            "source_path", "source_blob", "source_sha256", "trial_id_count", "trial_ids_unique",
            "agent_version", "source_jobs", "release_date", "trial_cost_completeness_verified"
        )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
