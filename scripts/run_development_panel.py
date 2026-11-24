"""Execute one frozen development panel on the explicitly authorized trusted runner.

Only redacted attestations and the plan/summary are published. Raw agent logs,
credentials and private job directories are excluded. Stop on unresolved
execution or financial state; untouched episodes remain missing in the summary.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.panel import build_panel
from cost_to_done.panel_results import summarize_panel, COMPLETE
from cost_to_done.private_files import publish_private_texts
from scripts.run_real_model_smoke import attestation


def _write(path: Path, record: dict) -> None:
    publish_private_texts([(path, json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n")])


def execute_panel(root: Path, output: Path, key: Path, plan: dict) -> dict:
    """Execute in frozen serial order with fresh per-episode ledgers."""
    if output.exists() or output.is_symlink():
        raise ReceiptError("panel output must be new")
    output.mkdir(mode=0o700, parents=True)
    _write(output / "plan.json", plan)
    records = []
    for trial in plan["trials"]:
        # Recheck all declared input identities before a new paid episode.
        current = build_panel(root, repetitions=plan["repetitions"], seed=plan["seed"],
                              budget_per_trial=trial["estimated_admission_allowance_usd"],
                              max_total_usd=plan["declared_ceiling_usd"])
        if current != plan:
            break
        config = plan["configurations"][trial["configuration"]]
        tid = trial["trial_id"]
        cfg = LiveConfig(root, root / "tasks" / trial["task"],
                         root / "runs/development-panel", config["model"],
                         root / config["price_schedule"], key,
                         trial["estimated_admission_allowance_usd"], tid,
                         plan["harness"]["max_turns"], plan["harness"]["max_wall_seconds"],
                         config["api"], config["reasoning_effort"])
        try:
            result = execute_live(cfg, acknowledged=True)
        except (ReceiptError, OSError, ValueError):
            # An unexpected runner failure is not evidence of zero expense.
            result = {"status": "incomplete_or_uncertain"}
        result.update(api=config["api"], reasoning_effort=config["reasoning_effort"],
                      task_fixture=trial["task"])
        record = attestation(result, config["model"])
        record.update(trial_id=tid, plan_sha256=plan["plan_sha256"])
        # Price identity is the declared schedule; do not invent ledger evidence.
        if record["price_schedule_sha256"] is None:
            record["price_schedule_sha256"] = config["price_schedule_sha256"]
        _write(output / (tid + ".json"), record)
        records.append(record)
        print(json.dumps({"trial_id": tid, "status": record["trial_status"],
                          "verifier": record["harbor_trial_outcome"],
                          "rate_card_estimate_usd": record["gateway_rate_card_estimate_usd"]}), flush=True)
        partial = summarize_panel(plan, records)
        if partial["trials"][len(records)-1]["state"] not in ("pass", "fail"):
            break
    summary = summarize_panel(plan, records)
    _write(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Guard the paid path even if the workflow is accidentally invoked elsewhere.
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REPOSITORY") != "fraware/cost-to-done"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("CTD_PANEL_AUTHORIZED") != "1"):
        raise SystemExit("trusted first-attempt paid panel authorization missing")
    credential = os.environ.pop("CTD_OPENAI_SECRET", "")
    if not credential:
        raise SystemExit("provider credential unavailable; no episode executed")
    root = args.repo_root.resolve(strict=True)
    plan = build_panel(root, repetitions=3, budget_per_trial="1", max_total_usd="18")
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as tmp:
        key = Path(tmp) / "upstream.key"
        fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(credential)
        del credential
        summary = execute_panel(root, args.output, key, plan)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary["complete_matched_accounting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
