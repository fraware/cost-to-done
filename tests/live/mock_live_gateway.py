"""Test-only transport substitution for the real live gateway builder.

Authentication, request validation, SQLite accounting, and the secret mount
are the same as for live_gateway. Only the upstream transport is fictional.
Do not use this module for a commercial model.
"""
from __future__ import annotations

import http.client
import os
from pathlib import Path

from cost_to_done.gateway import UpstreamResponse, _LocalServer
from cost_to_done.live_gateway import build_gateway


def mock_transport(payload: bytes, key: str) -> UpstreamResponse:
    """Forward exclusively to the isolated mock service."""
    client = http.client.HTTPConnection("ctd_mock_provider", 8770, timeout=30)
    try:
        client.request(
            "POST", "/v1/chat/completions", body=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        response = client.getresponse()
        return UpstreamResponse(
            response.status,
            response.read(4_000_001),
            response.getheader("Content-Type", "application/octet-stream"),
        )
    finally:
        client.close()


def main() -> None:
    """Keep the real gateway's configuration/secret read path."""
    if os.environ.get("CTD_REHEARSAL_ONLY") != "1":
        raise SystemExit("mock transport can only run in the rehearsal fixture")
    gateway = build_gateway(
        key_file=Path("/run/secrets/ctd_provider_key"),
        price_file=Path("/run/prices.json"),
        ledger_file=Path("/evidence/ledger.sqlite3"),
        budget_usd=os.environ["CTD_BUDGET_USD"],
        gateway_token=os.environ["CTD_GATEWAY_TOKEN"],
    )
    gateway.transport = mock_transport
    with _LocalServer(("0.0.0.0", 8866), gateway) as server:
        print("Rehearsal gateway ready; commercial inference disabled", flush=True)
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
