"""Verify the committed JSON and static table against recomputed upstream facts."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ResultTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "data-source-path" in attrs:
            self.row = {"path": attrs["data-source-path"], "cells": [], "link": None}
        if self.row is not None:
            if tag in ("th", "td"):
                self.cell = []
            elif tag == "a":
                self.row["link"] = attrs.get("href")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.row is None:
            return
        if tag in ("th", "td") and self.cell is not None:
            self.row["cells"].append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr":
            self.rows.append(self.row)
            self.row = None


def money(value):
    return "Unavailable" if value is None else f"${Decimal(value):,.2f}"


def main():
    actual = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    committed = json.loads((ROOT / "docs/data/terminal-bench-4-1.json").read_text(encoding="utf-8"))
    if committed != actual:
        raise SystemExit("Committed aggregate snapshot differs from recomputation")
    parser = ResultTable()
    parser.feed((ROOT / "docs/terminal-bench.html").read_text(encoding="utf-8"))
    expected = actual["rows"]
    if len(parser.rows) != len(expected):
        raise SystemExit("Static table row count mismatch")
    for rendered, row in zip(parser.rows, expected, strict=True):
        link = actual["source_repository"] + "/blob/" + actual["source_commit"] + "/" + row["source_path"]
        cells = [str(row["reported_successes"]) + "/" + str(row["n_trials"]),
                 money(row["reported_inference_cost_usd"]),
                 "Undefined" if row["reported_successes"] == 0 else money(row["reported_inference_cost_per_success_usd"])]
        if (rendered["path"] != row["source_path"] or rendered["link"] != link
                or rendered["cells"][-3:] != cells):
            raise SystemExit("Static table differs from source: " + row["source_path"])
    print(f"Verified committed snapshot and all {len(expected)} static result rows.")


if __name__ == "__main__":
    main()
