"""Statically reject unsafe composed Docker topology for live gateway planning.

The input is the fully interpolated JSON output of `docker compose config`
using the trusted live overlay plus a dummy Harbor `main` service. This checks
only declared configuration. It cannot establish runtime network isolation or
exclude changes introduced by the full Harbor-generated Compose stack.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from .core import ReceiptError


def _networks(value: Any) -> set[str]:
    """Normalize Docker Compose network objects or lists."""
    if isinstance(value, dict):
        return set(value)
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return set(value)
    raise ReceiptError("missing or malformed Compose service network declarations")


def audit_live_compose(config: dict[str, Any]) -> dict[str, Any]:
    """Return nonsecret structural evidence; reject a potential egress bypass.

    Refuses additional services, task host mounts, published ports, privilege
    escalation, and access to the upstream provider secret by the agent.
    This does not verify behavior on a running Docker host.
    """
    if not isinstance(config, dict):
        raise ReceiptError("Compose configuration must be a JSON object")
    services = config.get("services")
    networks = config.get("networks")
    secrets = config.get("secrets")
    if not isinstance(services, dict) or set(services) != {"main", "ctd_gateway"}:
        raise ReceiptError("unexpected Compose services; only main and gateway are approved for the static check")
    if not isinstance(networks, dict) or not isinstance(secrets, dict):
        raise ReceiptError("Compose network or secret declarations missing")
    agent_network = networks.get("ctd_agent_net")
    provider_network = networks.get("ctd_provider_net")
    if not isinstance(agent_network, dict) or agent_network.get("internal") is not True:
        raise ReceiptError("agent network must be explicitly internal")
    if not isinstance(provider_network, dict):
        raise ReceiptError("gateway provider egress network missing")
    if set(secrets) != {"ctd_provider_key"} or not isinstance(secrets["ctd_provider_key"], dict):
        raise ReceiptError("exactly one dedicated Compose provider secret required")
    if not isinstance(secrets["ctd_provider_key"].get("file"), str):
        raise ReceiptError("provider secret must originate from an external file mount")
    main = services["main"]
    gateway = services["ctd_gateway"]
    if not isinstance(main, dict) or not isinstance(gateway, dict):
        raise ReceiptError("malformed Compose service")
    if _networks(main.get("networks")) != {"ctd_agent_net"}:
        raise ReceiptError("agent is attached outside its internal-only network")
    if _networks(gateway.get("networks")) != {"ctd_agent_net", "ctd_provider_net"}:
        raise ReceiptError("gateway must bridge only declared agent and provider networks")
    for label, service in (("main", main), ("ctd_gateway", gateway)):
        if service.get("ports") or service.get("network_mode") or service.get("privileged"):
            raise ReceiptError(f"{label} has published ports or privilege/network escape")
        if service.get("devices") or service.get("pid") == "host" or service.get("ipc") == "host":
            raise ReceiptError(f"{label} has unsupported device or host-namespace access")
        drops = service.get("cap_drop", [])
        if not isinstance(drops, list) or "ALL" not in drops:
            raise ReceiptError(f"{label} must drop default Linux capabilities")
        extra = service.get("cap_add", []) or []
        if not isinstance(extra, list) or set(extra).difference({"FOWNER", "DAC_OVERRIDE"}):
            raise ReceiptError(f"{label} contains an unapproved Linux capability")
        security_opts = service.get("security_opt", [])
        if not isinstance(security_opts, list) or not any(
            str(option).startswith("no-new-privileges") for option in security_opts
        ):
            raise ReceiptError(f"{label} must disable privilege escalation")
    if main.get("secrets") or main.get("volumes"):
        raise ReceiptError("agent must not receive Compose secrets or arbitrary host mounts in this stub")
    if gateway.get("read_only") is not True:
        raise ReceiptError("gateway filesystem must be read-only")
    provided = gateway.get("secrets")
    if not isinstance(provided, list) or len(provided) != 1:
        raise ReceiptError("gateway must mount exactly one provider credential secret")
    item = provided[0]
    source = item if isinstance(item, str) else item.get("source") if isinstance(item, dict) else None
    if source != "ctd_provider_key":
        raise ReceiptError("gateway secret mount does not match declared provider key")
    env_main = main.get("environment") or {}
    env_gateway = gateway.get("environment") or {}
    if not isinstance(env_main, dict) or not isinstance(env_gateway, dict):
        raise ReceiptError("Compose environment must be structured as a mapping")
    if any(name in env_main for name in ("OPENAI_API_KEY", "CTD_PROVIDER_KEY_FILE", "ANTHROPIC_API_KEY")):
        raise ReceiptError("agent environment contains a provider credential reference")
    if "CTD_GATEWAY_TOKEN" not in env_gateway or "CTD_BUDGET_USD" not in env_gateway:
        raise ReceiptError("gateway missing authentication or accounting configuration")
    return {
        "status": "declared_topology_passes_static_check",
        "scope": "docker-compose-config-only_not_a_runtime_security_proof",
        "agent_network_internal": True,
        "gateway_bridges_two_declared_networks": True,
        "provider_secret_mounted_only_in_gateway": True,
        "public_port_bindings": 0,
    }


def main() -> int:
    """Audit Docker Compose JSON received on standard input without echoing it."""
    try:
        body = json.load(sys.stdin)
        print(json.dumps(audit_live_compose(body), sort_keys=True))
        return 0
    except (ValueError, TypeError, ReceiptError) as exc:
        print(f"invalid live gateway topology: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
