"""Command line interface for validating JSONL evidence and rendering reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ReceiptError, analyze, read_trials
from .execute import Launch, execute, plan
from .harbor import inspect_harbor_job, write_harbor_receipts
from .report import write_report


def main(argv: list[str] | None = None) -> int:
    """Return exit status 0 on valid input, 2 on user/configuration errors."""
    parser = argparse.ArgumentParser(prog="cost-to-done", description="Cost per verified completion from task-level receipts")
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "report"):
        p = subs.add_parser(command)
        p.add_argument("input", type=Path, help="JSONL of completed trial receipts")
        if command == "report":
            p.add_argument("--output", type=Path, default=Path("report.html"))
            p.add_argument("--title", default="Evaluation report")
            p.add_argument("--demo", action="store_true", help="Mark report as synthetic example; for bundled fixture only")
    p = subs.add_parser("import-harbor", help="Normalize pinned Harbor trial results (estimates, not invoices)")
    p.add_argument("manifest", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = subs.add_parser("inspect-harbor", help="Inspect raw Harbor job outcomes and cost availability")
    p.add_argument("job", type=Path, help="Harbor job directory containing trial result files")
    p.add_argument("--reward-key", default="reward", help="named scalar verifier reward")
    p = subs.add_parser("run-harbor", help="Plan or explicitly execute one real Harbor model trial")
    p.add_argument("--task", type=Path, default=Path("tasks/allocation-repair"))
    p.add_argument("--jobs-dir", type=Path, default=Path("runs"))
    p.add_argument("--model", required=True, help="Explicit provider/model route")
    p.add_argument("--agent", default="pi")
    p.add_argument("--job-name", default="cost-to-done-smoke")
    p.add_argument("--max-wall-seconds", type=int, default=900)
    p.add_argument("--max-turns", type=int, default=10)
    p.add_argument("--execute", action="store_true", help="Run the model instead of printing a zero-spend plan")
    p.add_argument("--acknowledge-no-dollar-cap", action="store_true", help="Confirm provider-side spending controls are installed")
    args = parser.parse_args(argv)
    try:
        if args.command == "run-harbor":
            cfg = Launch(args.task, args.jobs_dir, args.model, args.agent, args.job_name, args.max_wall_seconds, args.max_turns)
            result = execute(cfg, acknowledged=args.acknowledge_no_dollar_cap) if args.execute else plan(cfg)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] in ("dry_run_only", "completed_with_cost_estimate", "completed_cost_unavailable") else 2
        if args.command == "inspect-harbor":
            print(json.dumps(inspect_harbor_job(args.job, reward_key=args.reward_key), indent=2))
            return 0
        if args.command == "import-harbor":
            count = write_harbor_receipts(args.manifest, args.output)
            print(f"Imported {count} trials to {args.output} (rate-card estimates)")
            return 0
        result = analyze(read_trials(args.input))
        if args.command == "report":
            write_report(result, args.output, title=args.title, demo=args.demo)
            print(f"HTML report: {args.output}")
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (OSError, UnicodeError, ReceiptError, ValueError) as exc:
        print(f"cost-to-done: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
