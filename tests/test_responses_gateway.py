"""Offline conformance for the opt-in native Responses metering route."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import Gateway, PriceSchedule, UpstreamResponse, _LocalServer
from cost_to_done.ledger import BudgetLedger
from cost_to_done.responses import ROUTE

MODEL = "mock-responses"
TOKEN = "local-test-token-at-least-24-characters"


def request(**extra):
    obj = {
        "model": MODEL, "input": [{"role": "user", "content": "Repair task"}],
        "max_output_tokens": 100,
        "tools": [{"type": "function", "name": "run",
                   "parameters": {"type": "object", "properties": {}}, "strict": False}],
    }
    obj.update(extra)
    return json.dumps(obj).encode()


def result(**extra):
    obj = {"object": "response", "model": MODEL, "status": "completed",
           "output": [], "usage": {"input_tokens": 100, "output_tokens": 40,
                                    "total_tokens": 140}}
    obj.update(extra)
    return json.dumps(obj).encode()


class ResponsesGatewayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ledger = BudgetLedger(Path(tmp.name) / "ledger.db", budget_usd="5")
        self.seen = []
        self.reply = UpstreamResponse(200, result())

        def sender(payload, key):
            self.seen.append(json.loads(payload))
            return self.reply

        self.gateway = Gateway(
            self.ledger, PriceSchedule(MODEL, "2026-11-23",
                                       "https://example.com/prices", "20", "40"),
            client_token=TOKEN, provider_key="provider-key", transport=sender,
            route=ROUTE)

    def test_settles_and_preserves_bytes(self):
        self.assertEqual(self.gateway.handle(request(), "first"), (200, result()))
        self.assertEqual(self.ledger.snapshot().settled, "0.0036")
        self.assertEqual(self.ledger.snapshot().uncertain, 0)
        self.assertIs(self.seen[0]["store"], False)
        self.assertEqual(self.seen[0]["include"], ["reasoning.encrypted_content"])

    def test_stateless_tool_continuation(self):
        items = [
            {"role": "user", "content": "Repair task"},
            {"type": "reasoning", "id": "rs_1", "summary": [],
             "encrypted_content": "mock-opaque"},
            {"type": "function_call", "id": "fc_1", "call_id": "call_1",
             "name": "run", "arguments": "{}", "status": "completed"},
            {"type": "function_call_output", "call_id": "call_1", "output": "passed"},
        ]
        self.gateway.handle(request(input=items), "continuation")
        self.assertEqual(self.seen[0]["input"], items)

    def test_disallowed_requests_never_reserve_or_forward(self):
        for extra in (
            {"store": True}, {"stream": "true"}, {"background": True},
            {"previous_response_id": "resp_1"}, {"conversation": "conv_1"},
            {"tools": [{"type": "web_search"}]}, {"max_output_tokens": True},
            {"max_output_tokens": 4097}, {"model": "other"},
            {"input": [{"role": "user", "content": [{"type": "input_image"}]}]},
            {"input": [{"type": "item_reference", "id": "msg_1"}]},
            {"input": [{"type": "reasoning", "id": "rs_1", "summary": []}]},
            {"input": [{"type": "function_call_output", "call_id": "1", "output": []}]},
        ):
            with self.subTest(extra=extra), self.assertRaises(ReceiptError):
                self.gateway.handle(request(**extra), "bad")
        with self.assertRaises(ReceiptError):
            self.gateway.handle(request()[:-1] + b', "model": "mock-responses"}', "dup")
        self.assertEqual(self.seen, [])
        self.assertEqual(self.ledger.entries(), [])

    def test_incomplete_response_with_usage_is_charged(self):
        self.reply = UpstreamResponse(200, result(status="incomplete"))
        self.gateway.handle(request(), "incomplete")
        self.assertEqual(self.ledger.snapshot().settled, "0.0036")

    def test_bad_provider_usage_retains_reservation(self):
        cases = [
            result(model="wrong"), result(status="in_progress"), result(usage=None),
            result(usage={"input_tokens": 100, "output_tokens": 40, "total_tokens": 139}),
            result(usage={"input_tokens": 100, "output_tokens": 101, "total_tokens": 201}),
            result(usage={"input_tokens": True, "output_tokens": 40, "total_tokens": 41}),
        ]
        for i, payload in enumerate(cases):
            self.reply = UpstreamResponse(200, payload)
            with self.subTest(i=i), self.assertRaises(ReceiptError):
                self.gateway.handle(request(), f"uncertain-{i}")
        self.assertEqual(self.ledger.snapshot().uncertain, len(cases))
        self.assertEqual(self.ledger.snapshot().settled, "0")

    def test_http_dispatch_is_route_specific(self):
        with _LocalServer(("127.0.0.1", 0), self.gateway) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for path, expected in (("/v1/chat/completions", 404), (ROUTE, 200)):
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                    try:
                        conn.request("POST", path, request(),
                                     {"Authorization": "Bearer " + TOKEN})
                        response = conn.getresponse()
                        self.assertEqual(response.status, expected)
                        response.read()
                    finally:
                        conn.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)
        self.assertEqual(len(self.seen), 1)


def stream(*, status="completed", model=MODEL, terminal=True):
    start = {"object": "response", "id": "resp_test", "model": model,
             "status": "in_progress", "usage": None}
    end = json.loads(result(status=status, model=model))
    end["id"] = "resp_test"
    events = [
        {"type": "response.created", "sequence_number": 0, "response": start},
        {"type": "response.output_item.added", "sequence_number": 1,
         "item": {"type": "function_call", "id": "fc_1", "name": "run",
                  "call_id": "call_1", "arguments": "", "status": "in_progress"}},
        {"type": "response.function_call_arguments.delta", "sequence_number": 2,
         "item_id": "fc_1", "delta": "{}"},
    ]
    if terminal:
        events.append({"type": "response." + status, "sequence_number": 3, "response": end})
    return b"".join(b"event: " + e["type"].encode() + b"\ndata: "
                    + json.dumps(e).encode() + b"\n\n" for e in events)


class ResponsesStreamingTests(unittest.TestCase):
    setUp = ResponsesGatewayTests.setUp
    def test_stream_preserves_raw_bytes(self):
        for i, status in enumerate(("completed", "incomplete")):
            raw = stream(status=status)
            self.reply = UpstreamResponse(200, raw, "text/event-stream; charset=utf-8")
            self.assertEqual(self.gateway.handle(request(stream=True), f"ok-{i}"), (200, raw))
        self.assertEqual(self.ledger.snapshot().settled, "0.0072")
        self.assertEqual(self.ledger.snapshot().uncertain, 0)

    def test_bad_stream_reservations_are_retained(self):
        raw = stream()
        cases = [
            stream(terminal=False), stream(model="wrong"), stream(status="failed"),
            raw[:-1], raw + raw,
            raw.replace(b'"sequence_number": 2', b'"sequence_number": 9'),
            raw.replace(b'event: response.completed', b'event: response.incomplete'),
            raw.replace(b'"total_tokens": 140', b'"total_tokens": 139'),
            raw.replace(b'"status": "completed"', b'"status": "incomplete"'),
            raw.replace(b'"output_tokens": 40', b'"output_tokens": 400'),
        ]
        for i, body in enumerate(cases):
            self.reply = UpstreamResponse(200, body, "text/event-stream")
            with self.subTest(i=i), self.assertRaises(ReceiptError):
                self.gateway.handle(request(stream=True), f"bad-stream-{i}")
        self.assertEqual(self.ledger.snapshot().uncertain, len(cases))
        self.assertEqual(self.ledger.snapshot().settled, "0")

    def test_http_named_events_use_sse_content_type(self):
        raw = stream()
        self.reply = UpstreamResponse(200, raw, "text/event-stream")
        with _LocalServer(("127.0.0.1", 0), self.gateway) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                try:
                    conn.request("POST", ROUTE, request(stream=True),
                                 {"Authorization": "Bearer " + TOKEN})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
                    self.assertEqual(response.read(), raw)
                finally:
                    conn.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)
        self.assertEqual(self.ledger.snapshot().settled, "0.0036")
