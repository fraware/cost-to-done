"""Local mock OpenAI stream for tracing Pi's outbound request format.

Captures one deliberately synthetic request, not API credentials. Never forwards
traffic to the internet or executes an agent's tool invocations.
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    output: Path
    write_lock = threading.Lock()

    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        if self.path != '/ready':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != '/v1/chat/completions':
            self.send_error(404)
            return
        if self.headers.get('Authorization') != 'Bearer mock-pi-only-token':
            self.send_error(403)
            return
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length <= 1_000_000:
                raise ValueError('request is too large')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or body.get('model') != 'test-model-1':
                raise ValueError('unexpected model')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.send_error(400)
            return
        with self.write_lock:
            # This request contains only a publicly defined test prompt.
            # Authorization headers and environment variables are never saved.
            self.output.write_text(json.dumps(body, indent=2, sort_keys=True), encoding='utf-8')

        if not body.get('stream', False):
            response = json.dumps({'id': 'mock-pi-1', 'object': 'chat.completion',
                'model': 'test-model-1',
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': 'OK'}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        def chunk(delta: dict, finish: str | None = None) -> dict:
            return {'id': 'mock-pi-1', 'object': 'chat.completion.chunk',
                    'created': 0, 'model': 'test-model-1',
                    'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
        items = [chunk({'role': 'assistant'}), chunk({'content': 'OK'}),
                 chunk({}, 'stop'),
                 {'id': 'mock-pi-1', 'object': 'chat.completion.chunk',
                  'created': 0, 'model': 'test-model-1', 'choices': [],
                  'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'total_tokens': 11}}]
        data = b''.join(b'data: ' + json.dumps(obj).encode() + b'\n\n' for obj in items) + b'data: [DONE]\n\n'
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    Handler.output = args.output
    ThreadingHTTPServer(('127.0.0.1', 8877), Handler).serve_forever()
