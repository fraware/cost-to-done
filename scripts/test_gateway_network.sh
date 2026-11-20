#!/usr/bin/env bash
# End-to-end deterministic proof of Docker network separation and admission.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
project="ctdgw${GITHUB_RUN_ID:-local$$}"
compose=(docker compose -p "$project" -f tests/network/compose.yaml)
cleanup() {
  rc=$?
  if (( rc != 0 )); then
    "${compose[@]}" logs --no-color || true
  fi
  "${compose[@]}" down -v --remove-orphans || true
}
trap cleanup EXIT

"${compose[@]}" up --quiet-pull --wait -d provider gateway
provider_container=$("${compose[@]}" ps -q provider)
if [[ -z "$provider_container" ]]; then echo 'missing provider container' >&2; exit 1; fi
network_json=$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$provider_container")
provider_ip=$(python -c 'import json,sys; nets=json.loads(sys.argv[1]); ips=[v["IPAddress"] for k,v in nets.items() if k.endswith("_provider_net")]; assert len(ips)==1 and ips[0], nets; print(ips[0])' "$network_json")
"${compose[@]}" run --no-deps --rm -e "PROVIDER_IP=$provider_ip" agent
"${compose[@]}" exec -T provider python -c 'from pathlib import Path; p=Path("/tmp/mock-provider-requests.log"); assert p.read_text().splitlines() == ["forwarded"], p.read_text()'
"${compose[@]}" exec -T gateway python -c 'from cost_to_done.ledger import BudgetLedger; x=BudgetLedger("/tmp/gateway-ledger.sqlite3"); assert x.snapshot().settled == "0.0036", x.snapshot(); assert x.snapshot().pending == x.snapshot().uncertain == 0; assert len(x.entries()) == 1'
echo 'PASS: simulated agent metering and direct-bypass checks'

# Real Pi now runs on the same isolated agent network with a separate mock
# gateway ledger. No host ports, provider credentials or paid model calls.
"${compose[@]}" up --quiet-pull --wait -d pi_gateway
"${compose[@]}" build pi_agent
"${compose[@]}" run --no-deps --rm -e "PROVIDER_IP=$provider_ip" pi_agent
"${compose[@]}" exec -T pi_gateway python -c 'from cost_to_done.ledger import BudgetLedger; x=BudgetLedger("/tmp/pi-gateway-ledger.sqlite3"); assert x.snapshot().settled == "0.0036", x.snapshot(); assert x.snapshot().pending == x.snapshot().uncertain == 0; assert len(x.entries()) == 1'
"${compose[@]}" exec -T provider python -c 'from pathlib import Path; p=Path("/tmp/mock-provider-requests.log"); assert p.read_text().splitlines() == ["forwarded", "forwarded"], p.read_text()'
echo 'PASS: real Pi container completed through the streaming gateway; both mock provider calls fully accounted'
