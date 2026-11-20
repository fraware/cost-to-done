"""Run a fail-closed network bypass probe inside the actual Harbor task.

A successful proof means the tested agent container reached the mock gateway
and failed direct TCP connections to provider DNS, its raw IPv4 address, and a
public IPv4 endpoint. It is not a general isolation proof.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
from pathlib import Path


class IsolationError(RuntimeError):
    """An unexpected reachable endpoint or missing test precondition."""


def assert_blocked(host: str, port: int, *, label: str) -> None:
    """Reject a successful TCP handshake; network errors represent blocking."""
    try:
        connection = socket.create_connection((host, port), timeout=1.5)
    except OSError:
        return
    else:
        connection.close()
        raise IsolationError(f"direct-bypass succeeded: {label} {host}:{port}")


def provider_ip(path: Path, timeout: float = 20.0) -> str:
    """Read the provider address written at its startup; never guess the IP."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            source = path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            time.sleep(0.25)
            continue
        address = ipaddress.ip_address(source)
        if not isinstance(address, ipaddress.IPv4Address) or not address.is_private:
            raise IsolationError(f"unsafe provider bypass-test address: {source}")
        return source
    raise IsolationError("provider address proof was not created")


def main() -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CTD_MOCK_PROVIDER_KEY"):
        if os.environ.get(name):
            raise IsolationError(f"provider credential leaked to agent: {name}")
    if "mock-provider-key" in json.dumps(dict(os.environ)):
        raise IsolationError("mock provider credential leaked to agent environment")

    evidence = Path("/evidence")
    address = provider_ip(evidence / "provider-ip.txt")
    # Positive control prevents a false pass from an entirely disconnected task.
    try:
        with socket.create_connection(("ctd_mock_gateway", 8866), timeout=4):
            pass
    except OSError as exc:
        raise IsolationError("the actual agent cannot reach the metering gateway") from exc

    assert_blocked("ctd_mock_provider", 8770, label="provider DNS")
    assert_blocked(address, 8770, label="provider raw IPv4")
    assert_blocked("1.1.1.1", 443, label="public raw IPv4")
    proof = {
        "schema_version": 1,
        "subject": "Harbor main service at container startup",
        "gateway_reachable": True,
        "direct_provider_dns_blocked": True,
        "direct_provider_ip_blocked": True,
        "public_ip_blocked": True,
        "provider_ip_tested": address,
        "upstream_provider_credential_present": False,
        "mock_only": True,
    }
    (evidence / "harbor-agent-egress-proof.json").write_text(
        json.dumps(proof, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print("PASS: Harbor task startup network bypass probes", flush=True)


if __name__ == "__main__":
    main()
