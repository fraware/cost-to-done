"""Create a fully synthetic demonstration. No model endpoints are contacted."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent


def digest(text: str) -> str:
    """Stable synthetic reference hash for demo-only task and verifier IDs."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    """Write 90 hypothetical trials with varied costs, passes, and retries."""
    rows = []
    for config in range(5):
        for task in range(6):
            for replica in range(3):
                outcome = (config + 2 * task + replica) % 6 >= (2 if config < 3 else 3)
                retry = (task + replica + config) % 4 == 0
                base = (config + 1) * (task + 2)
                attempts = []
                if retry:
                    attempts.append({"cost_usd": f"{base * 0.0009:.6f}", "seconds": 12.0, "outcome": "fail", "cost_source": "rate_card_estimate"})
                attempts.append({"cost_usd": f"{base * 0.0011:.6f}", "seconds": 19.0 + task, "outcome": "pass" if outcome else "fail", "cost_source": "rate_card_estimate"})
                rows.append({
                    "trial_id": f"demo-{config+1}-{task+1}-{replica+1}",
                    "task_id": f"synthetic-task-{task+1:02d}",
                    "configuration_id": f"Hypothetical setup {chr(65+config)}",
                    "task_digest": digest(f"fictional-task-{task+1}"),
                    "verifier_digest": digest(f"fictional-tests-{task+1}"),
                    "harness_digest": digest(f"fictional-harness-{config+1}"),
                    "retry_policy": "one-feedback-retry",
                    "attempts": attempts,
                })
    out = ROOT / "synthetic-trials.jsonl"
    out.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"Created {len(rows)} synthetic trials at {out}")


if __name__ == "__main__":
    main()
