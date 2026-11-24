"""Create a fully synthetic demonstration. No model endpoints are contacted."""
from __future__ import annotations

import json
from pathlib import Path

from cost_to_done.demo import demo_rows


def main() -> None:
    rows = demo_rows()
    out = Path(__file__).parent / "synthetic-trials.jsonl"
    out.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"Created {len(rows)} synthetic trials at {out}")


if __name__ == "__main__":
    main()
