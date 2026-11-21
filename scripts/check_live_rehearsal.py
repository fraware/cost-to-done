"""Fail closed when a fake live gateway trial lacks verifier or ledger evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cost_to_done.harbor import inspect_harbor_job
from cost_to_done.ledger import BudgetLedger


def check(root: Path) -> dict:
    """Cross-check Harbor result, model turns, fake calls, and network probe."""
    session = root / ".sessions/rehearsal-scripted"
    evidence = session / "evidence"
    summary = json.loads((session / "run-summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "completed_with_unverified_rate_card_estimate":
        raise AssertionError("live runner did not finish cleanly")
    if summary.get("provider_invoice_reconciled") is not False or summary.get("provider_side_hard_cap_verified") is not False:
        raise AssertionError("mock must not claim invoiced charges or provider budget")
    inspected = inspect_harbor_job(root / "rehearsal-scripted")
    if inspected.get("complete") is not True or inspected.get("observed_trials") != 1:
        raise AssertionError("exactly one graded Harbor trial is necessary")
    trial = inspected["trials"][0]
    if (trial["agent"], trial["provider"], trial["model"], trial["outcome"]) != ("pi", "openai", "test-model-1", "pass"):
        raise AssertionError("expected scripted repair was not verified")
    transcripts = list((root / "rehearsal-scripted").glob("*/agent/pi.txt"))
    if len(transcripts) != 1:
        raise AssertionError("missing unique Pi transcript")
    events = [json.loads(x) for x in transcripts[0].read_text().splitlines() if x.startswith("{")]
    done = [e for e in events if e.get("type") == "message_end" and e.get("message", {}).get("role") == "assistant"]
    if len(done) < 2:
        raise AssertionError("the script must result in two model turns")
    ledger = BudgetLedger(evidence / "ledger.sqlite3")
    snapshot = ledger.snapshot()
    if (snapshot.settled != "0.0236" or snapshot.pending or snapshot.uncertain
            or snapshot.breached or len(ledger.entries()) != 2):
        raise AssertionError("mock metering did not reconcile")
    if (evidence / "provider-calls.txt").read_text().splitlines() != ["forwarded"] * 2:
        raise AssertionError("fake provider request count differs")
    proof = json.loads((evidence / "harbor-agent-egress-proof.json").read_text())
    checks = ("gateway_reachable", "direct_provider_dns_blocked", "direct_provider_ip_blocked", "public_ip_blocked")
    if proof.get("mock_only") is not True or any(proof.get(x) is not True for x in checks):
        raise AssertionError("agent network bypass proof missing or failed")
    return {
        "status": "isolated-live-runner-mock-verified",
        "mock_only": True, "billing_verified": False,
        "verifier_outcome": "pass", "gateway_calls": 2,
        "fictional_rate_card_usd": snapshot.settled,
        "harbor_trial_sha256": trial["raw_result_sha256"],
        "network_checks": list(checks),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_live_rehearsal.py JOBS_DIR")
    print(json.dumps(check(Path(sys.argv[1])), sort_keys=True, indent=2))
