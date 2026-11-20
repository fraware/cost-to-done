"""Reject a mock Harbor agent smoke run without a complete trial and verifier.

No mock usages in this check are asserted to be real provider charges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cost_to_done.harbor import inspect_harbor_job
from cost_to_done.ledger import BudgetLedger


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[2] != "--evidence":
        raise SystemExit("usage: check_harbor_mock.py JOB_DIR --evidence EVIDENCE_DIR")
    job_dir = Path(sys.argv[1])
    evidence = Path(sys.argv[3])
    result = inspect_harbor_job(job_dir)
    assert result["observed_trials"] == 1, result
    assert result["complete"] is True, result
    trial = result["trials"][0]
    assert trial["agent"] == "pi", trial
    assert trial["model"] == "test-model-1", trial
    assert trial["outcome"] == "fail", trial
    transcripts = list(job_dir.glob("*/agent/pi.txt"))
    assert len(transcripts) == 1, transcripts
    events = [json.loads(line) for line in transcripts[0].read_text().splitlines() if line.strip().startswith("{")]
    completed = [event["message"] for event in events if event.get("type") == "message_end"
                 and event.get("message", {}).get("role") == "assistant"
                 and event["message"].get("stopReason") == "stop"]
    assert len(completed) == 1 and completed[0]["usage"]["input"] > 0, completed
    assert completed[0]["usage"]["output"] > 0, completed
    ledger = BudgetLedger(evidence / "mock-ledger.sqlite3")
    snapshot = ledger.snapshot()
    assert snapshot.settled == "0.0036", snapshot
    assert snapshot.pending == snapshot.uncertain == 0, snapshot
    assert len(ledger.entries()) == 1, ledger.entries()
    assert (evidence / "provider-calls.txt").read_text().splitlines() == ["forwarded"]
    print(json.dumps({"status": "mock-harbor-trial-complete", "verifier_reward": 0,
                      "fictional_gateway_cost_usd": snapshot.settled, "gateway_forwarded_calls": 1,
                      "model": trial["model"], "agent": trial["agent"],
                      "billing_verified": False, "model_is_mock": True,
                      "verifier_artifact_sha256": trial.get("raw_result_sha256")}, indent=2))


if __name__ == "__main__":
    main()
