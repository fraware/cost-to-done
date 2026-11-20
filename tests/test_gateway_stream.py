"""Streaming receipt tests: terminal usage is required before settlement."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import Gateway, PriceSchedule, UpstreamResponse, _LocalServer
from cost_to_done.ledger import BudgetLedger

MODEL = 'test-model-1'
TOKEN = 'stream-mock-gateway-token-12345'


def request(**changes: object) -> bytes:
    payload: dict = {
        'model': MODEL,
        'messages': [{'role': 'system', 'content': 'Only solve the task'},
                     {'role': 'user', 'content': 'Hello'}],
        'max_completion_tokens': 100,
        'stream': True,
        'stream_options': {'include_usage': True},
        'store': False,
        'tools': [{'type': 'function', 'function': {
            'name': 'run', 'description': 'Execute a tool',
            'parameters': {'type': 'object', 'properties': {}}}}],
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def stream(*, model: str = MODEL, prompt: int = 100, completion: int = 40,
           finish: bool = True, usage: bool = True, done: bool = True) -> bytes:
    def frame(obj: dict) -> bytes:
        return b'data: ' + json.dumps(obj).encode() + b'\n\n'
    packets = [frame({'object': 'chat.completion.chunk', 'model': model,
        'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'OK'},
                     'finish_reason': None}]}),
        frame({'object': 'chat.completion.chunk', 'model': model,
        'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop' if finish else None}]})]
    if usage:
        packets.append(frame({'object': 'chat.completion.chunk', 'model': model,
            'choices': [], 'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}}))
    if done:
        packets.append(b'data: [DONE]\n\n')
    return b''.join(packets)


class StreamingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ledger = BudgetLedger(Path(tmp.name) / 'budget.db', budget_usd='5')
        self.price = PriceSchedule(MODEL, '2026-11-20',
                                   'https://example.com/fictional-prices', '20', '40')
        self.seen = []
        def sender(payload: bytes, secret: str) -> UpstreamResponse:
            self.seen.append((payload, secret))
            return UpstreamResponse(200, stream(), 'text/event-stream; charset=utf-8')
        self.gw = Gateway(self.ledger, self.price, client_token=TOKEN,
                          provider_key='mock-provider-key', transport=sender)

    def test_settle_complete_stream_and_preserve_raw_frames(self):
        data = stream()
        status, raw = self.gw.handle(request(), 'stream-okay')
        self.assertEqual(status, 200)
        self.assertEqual(raw, data)
        self.assertEqual(self.ledger.snapshot().settled, '0.0036')
        self.assertEqual(self.ledger.snapshot().uncertain, 0)
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(json.loads(self.seen[0][0])['stream'])

    def test_invalid_streaming_options_are_rejected_before_forwarding(self):
        for extra in (
            {'stream_options': None}, {'stream_options': {'include_usage': False}},
            {'stream_options': {'include_usage': True, 'unsupported': 1}},
            {'store': True}, {'stream': 'true'}, {'max_completion_tokens': 9999},
        ):
            with self.subTest(extra=extra), self.assertRaises(ReceiptError):
                self.gw.handle(request(**extra), 'bad-request')
        self.assertEqual(self.seen, [])
        self.assertEqual(self.ledger.entries(), [])

    def test_incomplete_or_malformed_streams_hold_authorization(self):
        cases = [
            stream(done=False), stream(usage=False), stream(finish=False),
            stream(model='other-model'), stream(prompt=99999999),
            stream(completion=101), stream()[:-4],
            stream().replace(b'data: [DONE]', b'data: BAD-DONE'),
        ]
        for i, body in enumerate(cases):
            self.gw.transport = lambda _payload, _key, body=body: UpstreamResponse(200, body, 'text/event-stream')
            with self.subTest(i=i), self.assertRaises(ReceiptError):
                self.gw.handle(request(), f'uncertain-{i}')
        self.assertEqual(self.ledger.snapshot().uncertain, len(cases))
        self.assertEqual(self.ledger.snapshot().settled, '0')

    def test_wrong_content_type_is_uncertain(self):
        self.gw.transport = lambda _body, _key: UpstreamResponse(200, stream(), 'application/json')
        with self.assertRaisesRegex(ReceiptError, 'content type'):
            self.gw.handle(request(), 'type-mismatch')
        self.assertEqual(self.ledger.snapshot().uncertain, 1)

    def test_http_stream_content_type_and_ledger(self):
        server = _LocalServer(('127.0.0.1', 0), self.gw)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            conn.request('POST', '/v1/chat/completions', request(), headers={
                'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json',
                'X-Cost-To-Done-Request-Id': 'http-stream'
            })
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Content-Type'), 'text/event-stream')
            self.assertEqual(response.read(), stream())
        finally:
            conn.close()
        self.assertEqual(self.ledger.snapshot().settled, '0.0036')


if __name__ == '__main__':
    unittest.main()
