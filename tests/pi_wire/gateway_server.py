"""Pi streaming compatibility test, with a fully mocked provider transport."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cost_to_done.gateway import Gateway, PriceSchedule, UpstreamResponse, _LocalServer
from cost_to_done.ledger import BudgetLedger


def stream() -> bytes:
    def frame(delta: dict, finish: str | None = None) -> bytes:
        value = {'id': 'pi-gateway-mock', 'object': 'chat.completion.chunk',
                 'created': 0, 'model': 'test-model-1',
                 'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
        return b'data: ' + json.dumps(value).encode() + b'\n\n'
    final_usage = {'id': 'pi-gateway-mock', 'object': 'chat.completion.chunk',
                   'created': 0, 'model': 'test-model-1', 'choices': [],
                   'usage': {'prompt_tokens': 100, 'completion_tokens': 40,
                             'total_tokens': 140}}
    return (frame({'role': 'assistant'}) + frame({'content': 'OK'}) +
            frame({}, 'stop') + b'data: ' + json.dumps(final_usage).encode() +
            b'\n\ndata: [DONE]\n\n')


def mock_transport(_body: bytes, _provider_key: str) -> UpstreamResponse:
    return UpstreamResponse(200, stream(), 'text/event-stream')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    price = PriceSchedule('test-model-1', '2026-11-20',
                          'https://example.com/fictional-rates', '20', '40')
    ledger = BudgetLedger(args.ledger, budget_usd='5')
    gateway = Gateway(ledger, price, client_token='mock-pi-test-gateway-token-00001',
                      provider_key='fake-provider-never-used', transport=mock_transport)
    with _LocalServer(('127.0.0.1', 8878), gateway) as server:
        server.serve_forever(poll_interval=0.1)
