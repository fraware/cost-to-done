"""Command line interface for validating JSONL evidence and rendering reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import ReceiptError, analyze, read_trials
from .harbor import write_harbor_receipts
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
    args = parser.parse_args(argv)
    try:
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
