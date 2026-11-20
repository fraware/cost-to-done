"""Deterministic fake paid provider, reachable only from the gateway network.

This fixture uses no paid credentials and has no public network listeners.
The request counter is examined by the host after the probe completes.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

COUNT_PATH = Path('/tmp/mock-provider-requests.log')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        if self.path != '/v1/chat/completions' or self.headers.get('Authorization') != 'Bearer mock-provider-key':
            self.send_error(403)
            return
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length < 256_000:
                raise ValueError('invalid length')
            body = json.loads(self.rfile.read(length))
            if body.get('model') != 'test-model-1' or body.get('stream', False):
                raise ValueError('unexpected request')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.send_error(400)
            return

        with COUNT_PATH.open('a', encoding='utf-8') as record:
            record.write('forwarded\n')
        response = json.dumps({
            'id': 'mock-completion-1', 'object': 'chat.completion',
            'model': 'test-model-1',
            'choices': [{'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': 'Mock repair plan'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 40, 'total_tokens': 140},
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8770), Handler).serve_forever(poll_interval=0.1)
