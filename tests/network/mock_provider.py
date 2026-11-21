"""Deterministic fake paid provider, reachable only from the gateway network.

This fixture uses no paid credentials and has no public network listeners.
The request counter is examined by the host after the probe completes.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

COUNT_PATH = Path(os.environ.get('CTD_PROVIDER_LOG_PATH', '/tmp/mock-provider-requests.log'))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        expected_key = os.environ.get('CTD_MOCK_PROVIDER_KEY', 'mock-provider-key')
        if self.path != '/v1/chat/completions' or self.headers.get('Authorization') != f'Bearer {expected_key}':
            self.send_error(403)
            return
        try:
            length = int(self.headers['Content-Length'])
            if not 0 < length < 256_000:
                raise ValueError('invalid length')
            body = json.loads(self.rfile.read(length))
            if body.get('model') != 'test-model-1':
                raise ValueError('unexpected model')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.send_error(400)
            return

        scenario = os.environ.get('CTD_MOCK_SCENARIO', 'noop')
        if scenario == 'scripted-repair':
            from mock_repair import scripted_reply
            try:
                delta, finish_reason = scripted_reply(body)
            except (ValueError, TypeError):
                self.send_error(422, 'invalid scripted tool exchange')
                return
            tool_response = finish_reason == 'tool_calls'
            usage = {
                'prompt_tokens': 100 if tool_response else 200,
                'completion_tokens': 400 if tool_response else 40,
            }
        elif scenario == 'noop':
            delta, finish_reason = {'content': 'OK'}, 'stop'
            usage = {'prompt_tokens': 100, 'completion_tokens': 40}
        else:
            self.send_error(422, 'unsupported mock scenario')
            return
        usage['total_tokens'] = usage['prompt_tokens'] + usage['completion_tokens']

        with COUNT_PATH.open('a', encoding='utf-8') as record:
            record.write('forwarded\n')
        if body.get('stream', False):
            def frame(value: dict) -> bytes:
                return b'data: ' + json.dumps(value).encode('utf-8') + b'\n\n'
            def choice(delta: dict, finish: str | None = None) -> dict:
                return {'id': 'mock-completion-1', 'object': 'chat.completion.chunk',
                        'created': 0, 'model': 'test-model-1',
                        'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}
            final = {'id': 'mock-completion-1', 'object': 'chat.completion.chunk',
                     'created': 0, 'model': 'test-model-1', 'choices': [],
                     'usage': usage}
            response = (frame(choice({'role': 'assistant'})) + frame(choice(delta)) +
                        frame(choice({}, finish_reason)) + frame(final) + b'data: [DONE]\n\n')
            mime = 'text/event-stream'
        else:
            response = json.dumps({
                'id': 'mock-completion-1', 'object': 'chat.completion',
                'model': 'test-model-1',
                'choices': [{'index': 0, 'finish_reason': finish_reason,
                             'message': {'role': 'assistant', **delta}}],
                'usage': usage,
            }).encode('utf-8')
            mime = 'application/json'
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8770), Handler).serve_forever(poll_interval=0.1)
