"""Two-network gateway fixture using a real HTTP transport to a fake provider.

The gateway's mock provider credential is used only within this process.
Never substitute the mock provider transport for production upstream routing.
"""
from __future__ import annotations

import http.client
import os

from cost_to_done.gateway import Gateway, PriceSchedule, UpstreamResponse, _LocalServer
from cost_to_done.ledger import BudgetLedger


def mock_transport(body: bytes, key: str) -> UpstreamResponse:
    conn = http.client.HTTPConnection('provider', 8770, timeout=4)
    try:
        conn.request('POST', '/v1/chat/completions', body, headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'
        })
        response = conn.getresponse()
        return UpstreamResponse(response.status, response.read(256_000),
                                response.getheader("Content-Type", "application/octet-stream"))
    finally:
        conn.close()


if __name__ == '__main__':
    price = PriceSchedule('test-model-1', '2026-11-20',
                          'https://example.com/fictional-rates', '20', '40')
    pi_mode = os.environ.get('CTD_PI_MODE') == '1'
    ledger = BudgetLedger('/tmp/pi-gateway-ledger.sqlite3' if pi_mode else '/tmp/gateway-ledger.sqlite3',
                          budget_usd='5' if pi_mode else '0.05')
    gateway = Gateway(ledger, price, client_token='test-gateway-session-token-00001',
                      provider_key='mock-provider-key', transport=mock_transport)
    # This listener is reachable only on Compose's internal agent network.
    # The *mock* gateway also attaches to the provider network for test traffic.
    with _LocalServer(('0.0.0.0', 8866 if pi_mode else 8766), gateway) as server:
        server.serve_forever(poll_interval=0.1)
