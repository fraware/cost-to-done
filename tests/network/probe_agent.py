"""Fail-closed simulated agent: access must pass through the metered gateway."""
from __future__ import annotations

import http.client
import json
import os
import socket
from urllib.parse import urlparse

MODEL = 'test-model-1'
TOKEN = 'test-gateway-session-token-00001'


def request(*, request_id: str, completion_tokens: int = 100,
            token: str = TOKEN) -> tuple[int, dict]:
    conn = http.client.HTTPConnection('gateway', 8766, timeout=5)
    data = json.dumps({'model': MODEL, 'messages': [{'role': 'user', 'content': 'Fix the allocation issue'}],
                       'max_completion_tokens': completion_tokens}).encode()
    try:
        conn.request('POST', '/v1/chat/completions', body=data, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token,
            'X-Cost-To-Done-Request-Id': request_id,
        })
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


def assert_unreachable(address: str, port: int, *, label: str) -> None:
    try:
        with socket.create_connection((address, port), timeout=1):
            raise AssertionError(f'ISOLATION FAILURE: agent reached {label} at {address}:{port}')
    except (socket.timeout, ConnectionRefusedError, OSError):
        # A network error is the desired result. An established TCP session
        # raises the AssertionError above instead of being accepted.
        return


def main() -> None:
    assert 'OPENAI_API_KEY' not in os.environ, 'provider credential leaked to agent'
    assert 'ANTHROPIC_API_KEY' not in os.environ, 'provider credential leaked to agent'
    assert 'mock-provider-key' not in json.dumps(dict(os.environ)), 'mock provider secret leaked'
    provider_ip = os.environ.get('PROVIDER_IP')
    assert provider_ip, 'host did not supply the direct-bypass test IP'

    assert_unreachable('provider', 8770, label='provider DNS name')
    assert_unreachable(provider_ip, 8770, label='provider raw IP')
    assert_unreachable('1.1.1.1', 443, label='public internet raw IP')

    status, _ = request(request_id='wrong-credential', token='not-authorized')
    assert status == 401, f'unauthenticated request returned {status}'
    status, response = request(request_id='allowed-001')
    assert status == 200 and response.get('model') == MODEL, (status, response)
    assert response['usage']['completion_tokens'] == 40
    status, _ = request(request_id='allowed-001')
    assert status == 400, f'duplicate forwarded or incorrectly accepted: {status}'
    status, _ = request(request_id='over-budget', completion_tokens=4096)
    assert status == 402, f'over-budget request was forwarded: {status}'
    print('PASS: metered request and three independent direct-egress probes', flush=True)


if __name__ == '__main__':
    main()
