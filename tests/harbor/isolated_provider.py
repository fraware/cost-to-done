"""Launch the fictional model provider and expose its Docker IP to test probes.

Only CI uses this file. The address is published for a deliberate raw-IP
bypass attempt, never as a service discovery or production endpoint.
"""
from __future__ import annotations

import ipaddress
import os
import runpy
import socket
from pathlib import Path


def provider_ip() -> str:
    addresses = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET)
    candidates = [record[4][0] for record in addresses]
    for candidate in candidates:
        address = ipaddress.ip_address(candidate)
        if address.is_private and not address.is_loopback and not address.is_link_local:
            return candidate
    raise RuntimeError(f"no private container address found: {candidates}")


def main() -> None:
    path = Path(os.environ.get("CTD_PROVIDER_IP_PATH", "/evidence/provider-ip.txt"))
    path.write_text(provider_ip() + "\n", encoding="ascii")
    runpy.run_path("/fixture/mock_provider.py", run_name="__main__")


if __name__ == "__main__":
    main()
