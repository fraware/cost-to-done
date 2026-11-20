"""Audit a Harbor/Pi mock job AND its runtime direct-provider bypass proof.

The network proof comes from the actual agent container's startup probe. A
passing record covers only this Compose topology and the tested IP endpoints.
"""
from __future__ import annotations

import ipaddress
import json
import sys
from pathlib import Path

from cost_to_done.harbor import inspect_harbor_job
from cost_to_done.ledger import BudgetLedger


REQUIRED_CHECKS = frozenset({
    "gateway_reachable", "direct_provider_dns_blocked",
    "direct_provider_ip_blocked", "public_ip_blocked",
})


def verify(job_dir: Path, evidence: Path) -> dict[str, object]:
    proof = json.loads((evidence / "harbor-agent-egress-proof.json").read_text("utf-8"))
    assert proof.get("schema_version") == 1, proof
    assert proof.get("subject") == "Harbor main service at container startup", proof
    assert proof.get("mock_only") is True, proof
    assert proof.get("upstream_provider_credential_present") is False, proof
    assert all(proof.get(key) is True for key in REQUIRED_CHECKS), proof
    ip = str(ipaddress.IPv4Address(proof["provider_ip_tested"]))
    assert ipaddress.IPv4Address(ip).is_private, proof
    assert (evidence / "provider-ip.txt").read_text("ascii").strip() == ip

    inspected = inspect_harbor_job(job_dir)
    assert inspected["complete"] is True and inspected["observed_trials"] == 1, inspected
    trial = inspected["trials"][0]
    assert trial["agent"] == "pi" and trial["model"] == "test-model-1", trial
    assert trial["outcome"] == "fail", trial  # Mock model deliberately does no repair.
    sessions = list(job_dir.glob("*/agent/pi.txt"))
    assert len(sessions) == 1, sessions
    events = [json.loads(line) for line in sessions[0].read_text().splitlines()
              if line.strip().startswith("{")]
    finished = [e["message"] for e in events if e.get("type") == "message_end"
                and e.get("message", {}).get("role") == "assistant"
                and e["message"].get("stopReason") == "stop"]
    assert len(finished) == 1 and finished[0]["usage"]["input"] > 0, finished
    assert finished[0]["usage"]["output"] > 0, finished

    ledger = BudgetLedger(evidence / "mock-ledger.sqlite3")
    state = ledger.snapshot()
    assert state.settled == "0.0036" and state.pending == 0 and state.uncertain == 0, state
    assert len(ledger.entries()) == 1
    assert (evidence / "provider-calls.txt").read_text().splitlines() == ["forwarded"]
    return {
        "status": "mock-harbor-pi-isolated-verified",
        "network_checks": sorted(REQUIRED_CHECKS),
        "gateway_calls": 1,
        "mock_price_estimate_usd": state.settled,
        "verifier_outcome": "fail",
        "real_model_executed": False,
        "provider_invoice_verified": False,
        "harbor_trial_raw_sha256": trial.get("raw_result_sha256"),
    }


def main() -> None:
    if len(sys.argv) != 4 or sys.argv[2] != "--evidence":
        raise SystemExit("usage: check_harbor_isolated.py JOB_DIR --evidence EVIDENCE_DIR")
    print(json.dumps(verify(Path(sys.argv[1]), Path(sys.argv[3])), indent=2))


if __name__ == "__main__":
    main()
