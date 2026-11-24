"""Entrypoint for an isolated, non-public, provider-key-holding gateway container.

Only the gateway service receives the upstream key as a Docker Compose secret.
The listening interface is container-local to the explicitly configured agent
network, not intended for port publication or internet exposure. Cost limits
are conservative estimates; invoices must be reconciled independently.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .core import ReceiptError
from .gateway import Gateway, PriceSchedule, _LocalServer
from .ledger import BudgetLedger, _units

_PORT = 8866
_SECRET_FILE = Path("/run/secrets/ctd_provider_key")


def read_key(path: Path) -> str:
    """Read a bounded credential from a regular, gateway-only secret mount."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ReceiptError("missing or unsafe upstream secret mount")
    try:
        secret = path.read_text(encoding="ascii").strip()
    except (UnicodeError, OSError) as exc:
        raise ReceiptError("unreadable upstream secret mount") from exc
    if not 24 <= len(secret) <= 4096 or re.fullmatch(r"[^\s\x00-\x1f\x7f]+", secret) is None:
        raise ReceiptError("upstream credential has invalid length or format")
    return secret


def build_gateway(*, key_file: Path, price_file: Path, ledger_file: Path,
                  budget_usd: str, gateway_token: str,
                  route: str = "/v1/chat/completions") -> Gateway:
    """Validate configuration before constructing a network listener."""
    _units(budget_usd, allow_zero=False)
    if not isinstance(gateway_token, str) or len(gateway_token) < 32:
        raise ReceiptError("gateway session token too short")
    price = PriceSchedule.load(price_file)
    key = read_key(key_file)
    ledger = BudgetLedger(ledger_file, budget_usd=budget_usd)
    return Gateway(ledger, price, client_token=gateway_token, provider_key=key,
                   max_output_cap=4096, route=route)


def main() -> None:
    """Run exclusively inside the constrained, unexposed Compose gateway."""
    gw = build_gateway(
        key_file=_SECRET_FILE,
        price_file=Path(os.environ.get("CTD_PRICE_PATH", "/run/prices.json")),
        ledger_file=Path(os.environ.get("CTD_LEDGER_PATH", "/evidence/ledger.sqlite3")),
        budget_usd=os.environ.get("CTD_BUDGET_USD", ""),
        gateway_token=os.environ.get("CTD_GATEWAY_TOKEN", ""),
        route=os.environ.get("CTD_GATEWAY_ROUTE", "/v1/chat/completions"),
    )
    with _LocalServer(("0.0.0.0", _PORT), gw) as server:
        print(f"Metered inference gateway ready; model={gw.price.model}; schedule_sha256={gw.price.digest}", flush=True)
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
