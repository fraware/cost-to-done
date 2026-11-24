"""Command line interface for validating JSONL evidence and rendering reports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import ReceiptError, analyze, parse_trial, read_trials
from .demo import demo_rows
from .live import LiveConfig, execute_live, plan_live, TRUSTED_TASK_MODULES
from .execute import Launch, execute, plan
from .evidence import EvidenceRequest, write_evidence_receipt
from .harbor import inspect_harbor_job, write_harbor_receipts
from .harbor_report import write_harbor_overview
from .harbor_compare import write_harbor_comparison
from .gateway import PriceSchedule, serve_local
from .ledger import BudgetLedger
from .report import write_report
from .panel import build_panel
from .panel_results import summarize_panel
from .private_files import publish_private_texts


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
    p = subs.add_parser("demo", help="Generate a clearly labeled synthetic report; no API key or repository needed")
    p.add_argument("--output", type=Path, default=Path("cost-to-done-demo.html"))
    p = subs.add_parser("prepare-repo-task", help="Package explicitly selected committed Python files as an unqualified Harbor task; no inference")
    p.add_argument("--repository", type=Path, required=True)
    p.add_argument("--revision", default="HEAD", help="HEAD or exact full commit hash")
    p.add_argument("--name", required=True)
    p.add_argument("--source", action="append", required=True, help="Committed source path; repeat for each file")
    p.add_argument("--test", action="append", required=True, help="Committed test_*.py path; repeat for each test module")
    p.add_argument("--instruction", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="New task directory with an existing parent")
    p = subs.add_parser("validate-repo-task", help="Check prepared task files and reject undeclared build inputs; no execution")
    p.add_argument("task", type=Path)
    p = subs.add_parser("qualify-repo-task", help="Bind matched starter/reference nop controls to a prepared task; no inference")
    p.add_argument("--starter", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--starter-job", type=Path, required=True)
    p.add_argument("--reference-job", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = subs.add_parser("plan-panel", help="Freeze the bundled matched native development panel; no inference")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--repetitions", type=int, default=1)
    p.add_argument("--seed", type=int, default=20261124)
    p.add_argument("--budget-per-trial", default="1")
    p.add_argument("--max-total-usd", default="6")
    p.add_argument("--output", type=Path, help="Optional new private plan JSON file")
    p = subs.add_parser("summarize-panel", help="Recompute accounting from a frozen panel and redacted observations")
    p.add_argument("directory", type=Path, help="Directory containing plan.json and individual trial JSON records")
    p.add_argument("--output", type=Path, help="Optional new private summary JSON file")
    p = subs.add_parser("report-panel", help="Render an offline, unranked report from planned episodes and raw attestations")
    p.add_argument("directory", type=Path)
    p.add_argument("--output", type=Path, default=Path("panel-report.html"))
    p = subs.add_parser("replay-candidate", help="Run pristine bundled tests against a source file in a fresh offline Docker container")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--task", choices=tuple(TRUSTED_TASK_MODULES), required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate", type=Path)
    source.add_argument("--harbor-job", type=Path, help="Job with an explicit candidate artifact collection manifest")
    p.add_argument("--output", type=Path, help="Optional new private replay evidence JSON")
    p = subs.add_parser("import-harbor", help="Normalize pinned Harbor trial results (estimates, not invoices)")
    p.add_argument("manifest", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p = subs.add_parser("compare-harbor", help="Generate an offline, unranked comparison of complete matched Harbor jobs")
    p.add_argument("jobs", nargs="+", help="2–8 named Harbor jobs in NAME=PATH form")
    p.add_argument("--output", type=Path, default=Path("harbor-comparison.html"))
    p.add_argument("--title", default="Harbor comparison")
    p = subs.add_parser("report-harbor", help="Render a standalone, unranked HTML overview from one Harbor job")
    p.add_argument("job", type=Path, help="Existing Harbor job directory")
    p.add_argument("--output", type=Path, default=Path("harbor-evidence.html"))
    p.add_argument("--title", default="Harbor run")
    p = subs.add_parser("inspect-harbor", help="Inspect raw Harbor job outcomes and cost availability")
    p.add_argument("job", type=Path, help="Harbor job directory containing trial result files")
    p.add_argument("--reward-key", default="reward", help="named scalar verifier reward")
    p = subs.add_parser("reconcile-harbor", help="Join one Harbor trial to a dedicated, fully settled inference ledger")
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--task", type=Path, required=True)
    p.add_argument("--verifier", type=Path, required=True)
    p.add_argument("--price-schedule", type=Path, required=True)
    p.add_argument("--configuration-id", required=True)
    p.add_argument("--agent", default="pi")
    p.add_argument("--model", required=True, help="Expected openai/model route")
    p.add_argument("--harness-digest", required=True, help="Operator-declared SHA-256 of a pinned harness specification")
    p.add_argument("--harbor-task-checksum", required=True, help="Expected Harbor task checksum from archived control evidence")
    p.add_argument("--output", type=Path, required=True, help="New JSONL receipt file, with adjacent provenance sidecar")
    p = subs.add_parser("run-harbor-gateway", help="Plan or explicitly execute the qualified task through an isolated metering gateway")
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--task", type=Path, default=Path("tasks/allocation-repair"))
    p.add_argument("--jobs-dir", type=Path, default=Path("runs"))
    p.add_argument("--model", required=True, help="Exact OpenAI model ID")
    p.add_argument("--api", choices=("chat", "responses"), default="chat")
    p.add_argument("--reasoning-effort", choices=("off", "low", "medium", "high", "xhigh"), default="low")
    p.add_argument("--price-schedule", required=True, type=Path)
    p.add_argument("--provider-key-file", required=True, type=Path,
                   help="Private chmod-600 file outside the repository; never pass key contents")
    p.add_argument("--budget-usd", required=True, help="Exact USD allowance for estimated gateway admission")
    p.add_argument("--repository-task-sha256", help="Separately pinned prepared task digest (external plan only)")
    p.add_argument("--repository-qualification", type=Path, help="Local starter/reference control receipt")
    p.add_argument("--job-name", default="gateway-smoke-01")
    p.add_argument("--max-turns", type=int, default=3)
    p.add_argument("--max-wall-seconds", type=int, default=900)
    p.add_argument("--execute", action="store_true", help="Opt in to a paid model trial")
    p.add_argument("--acknowledge-provider-limit", action="store_true",
                   help="Confirm independent provider-side spending controls and invoice uncertainty")
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
    p = subs.add_parser("gateway-serve", help="Start the opt-in, local non-streaming OpenAI inference gateway")
    p.add_argument("--price-schedule", required=True, type=Path)
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--budget-usd", required=True, help="Exact decimal run authorization amount")
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--serve", action="store_true", help="Actually bind the gateway; default is a no-spend plan")
    p.add_argument("--acknowledge-no-provider-hard-cap", action="store_true")
    p = subs.add_parser("gateway-status", help="Read local admission ledger without provider calls")
    p.add_argument("ledger", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            write_report(analyze([parse_trial(row) for row in demo_rows()]), args.output,
                         title="Synthetic comparison", demo=True)
            print(f"Synthetic demonstration (no measured model results): {args.output}")
            return 0
        if args.command == "prepare-repo-task":
            from .repository_task import prepare_repository_task
            result = prepare_repository_task(args.repository, revision=args.revision,
                                             name=args.name, sources=args.source, tests=args.test,
                                             instruction=args.instruction, output=args.output)
            print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
            return 0
        if args.command == "validate-repo-task":
            from .repository_task import validate_repository_task
            result = validate_repository_task(args.task)
            print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
            return 0
        if args.command == "qualify-repo-task":
            from .repository_qualification import qualify_repository_task
            result = qualify_repository_task(args.starter, args.reference, args.starter_job, args.reference_job)
            payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
            publish_private_texts([(args.output, payload)])
            print(payload, end="")
            return 0
        if args.command == "plan-panel":
            panel = build_panel(args.repo_root, repetitions=args.repetitions, seed=args.seed,
                                budget_per_trial=args.budget_per_trial, max_total_usd=args.max_total_usd)
            payload = json.dumps(panel, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if args.output is not None:
                publish_private_texts([(args.output, payload)])
            print(payload, end="")
            return 0
        if args.command == "summarize-panel":
            from .panel_results import read_panel_directory
            panel, observations = read_panel_directory(args.directory)
            result = summarize_panel(panel, observations)
            payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if args.output is not None:
                publish_private_texts([(args.output, payload)])
            print(payload, end="")
            return 0
        if args.command == "report-panel":
            from .panel_report import write_panel_report
            write_panel_report(args.directory, args.output)
            print(f"Offline development-panel report: {args.output}")
            return 0
        if args.command == "replay-candidate":
            from .replay import captured_candidate, replay_candidate
            if args.output is not None and (args.output.exists() or args.output.is_symlink()):
                raise ReceiptError("replay output already exists")
            candidate = (captured_candidate(args.harbor_job, args.task)
                         if args.harbor_job is not None else args.candidate)
            result = replay_candidate(args.repo_root, args.task, candidate)
            payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if args.output is not None:
                publish_private_texts([(args.output, payload)])
            print(payload, end="")
            return {"pass": 0, "fail": 1, "unresolved": 2}[result["outcome"]]
        if args.command == "gateway-status":
            ledger = BudgetLedger(args.ledger)
            print(json.dumps({"snapshot": ledger.snapshot().to_dict(), "entries": ledger.entries()}, indent=2))
            return 0
        if args.command == "gateway-serve":
            schedule = PriceSchedule.load(args.price_schedule)
            # Exact monetary argument is validated even in dry run. Never create a
            # ledger or read credentials in plan mode.
            from .ledger import _units
            _units(args.budget_usd, allow_zero=False)
            if not args.serve:
                print(json.dumps({"status": "plan_only", "listen_host": "127.0.0.1",
                                  "port": args.port, "model": schedule.model,
                                  "price_schedule_sha256": schedule.digest,
                                  "budget_usd": args.budget_usd,
                                  "spending_basis": "rate_card_estimate_not_invoice",
                                  "provider_hard_cap": False}, indent=2))
                return 0
            if not args.acknowledge_no_provider_hard_cap:
                raise ReceiptError("--serve requires --acknowledge-no-provider-hard-cap")
            if os.name != "posix":
                raise ReceiptError("live gateway only supported on POSIX in this release")
            token = os.environ.get("COST_TO_DONE_GATEWAY_TOKEN", "")
            provider_key = os.environ.get("OPENAI_API_KEY", "")
            serve_local(ledger_path=args.ledger, budget_usd=args.budget_usd,
                        price_path=args.price_schedule, port=args.port,
                        gateway_token=token, provider_key=provider_key)
            return 0
        if args.command == "reconcile-harbor":
            request = EvidenceRequest(
                job=args.job, ledger=args.ledger, task=args.task, verifier=args.verifier,
                price_schedule=args.price_schedule, configuration_id=args.configuration_id,
                agent=args.agent, model=args.model, harness_digest=args.harness_digest,
                harbor_task_checksum=args.harbor_task_checksum,
            )
            print(json.dumps(write_evidence_receipt(request, args.output), indent=2))
            return 0
        if args.command == "run-harbor-gateway":
            cfg = LiveConfig(args.repo_root, args.task, args.jobs_dir, args.model,
                             args.price_schedule, args.provider_key_file, args.budget_usd,
                             args.job_name, args.max_turns, args.max_wall_seconds, args.api, args.reasoning_effort,
                             repository_task_sha256=args.repository_task_sha256,
                             repository_qualification=args.repository_qualification)
            if args.execute and (args.repository_task_sha256 is not None or args.repository_qualification is not None):
                raise ReceiptError("external repository execution remains mock-only")
            result = execute_live(cfg, acknowledged=args.acknowledge_provider_limit) if args.execute else plan_live(cfg)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] in ("plan_only", "completed_with_unverified_rate_card_estimate") else 2
        if args.command == "run-harbor":
            cfg = Launch(args.task, args.jobs_dir, args.model, args.agent, args.job_name, args.max_wall_seconds, args.max_turns)
            result = execute(cfg, acknowledged=args.acknowledge_no_dollar_cap) if args.execute else plan(cfg)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] in ("dry_run_only", "completed_with_cost_estimate", "completed_cost_unavailable") else 2
        if args.command == "compare-harbor":
            print(json.dumps(write_harbor_comparison(args.jobs, args.output, title=args.title), indent=2))
            return 0
        if args.command == "report-harbor":
            print(json.dumps(write_harbor_overview(args.job, args.output, title=args.title), indent=2))
            return 0
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
