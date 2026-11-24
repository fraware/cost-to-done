"""Mock-transport gateway checks: no provider credentials or external network."""
from __future__ import annotations

import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import (
    Gateway, PriceSchedule, UpstreamResponse, _LocalServer,
)
from cost_to_done.ledger import BudgetLedger


TOKEN = "gateway-session-token-example-0001"
SECRET = "upstream-provider-api-key"
MODEL = "test-model-1"


def request(*, max_tokens: int = 100, model: str = MODEL, **extra):
    return json.dumps({"model": model, "messages": [{"role": "user", "content": "Fix the issue"}],
                       "max_completion_tokens": max_tokens, **extra}).encode()


def success(prompt=100, completion=40, *, model=MODEL):
    return UpstreamResponse(200, json.dumps({"id": "upstream-001", "model": model,
        "choices": [{"message": {"role": "assistant", "content": "done"}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion}}).encode())


class GatewayTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.price = PriceSchedule(MODEL, "2026-11-20", "https://example.com/price-source", "20", "40")
        self.seen = []

        def fake_upstream(body, secret):
            self.seen.append((json.loads(body), secret))
            return success()

        self.ledger = BudgetLedger(self.root / "ledger.sqlite3", budget_usd="0.1")
        self.gateway = Gateway(self.ledger, self.price, client_token=TOKEN, provider_key=SECRET,
                               transport=fake_upstream)

    def test_successful_forwarding_and_estimate(self):
        status, raw = self.gateway.handle(request(), "req-001")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["model"], MODEL)
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(self.seen[0][1], SECRET)
        self.assertEqual(self.ledger.snapshot().settled, "0.0036")
        self.assertEqual(self.ledger.snapshot().reserved, "0")

    def test_reject_budget_before_network(self):
        self.ledger.reserve("existing", "0.099")
        with self.assertRaisesRegex(ReceiptError, "admission denied"):
            self.gateway.handle(request(), "req-over-limit")
        self.assertEqual(self.seen, [])
        self.assertEqual(len(self.ledger.entries()), 1)

    def test_replay_does_not_forward_twice(self):
        self.gateway.handle(request(), "same-id")
        with self.assertRaisesRegex(ReceiptError, "duplicate request"):
            self.gateway.handle(request(), "same-id")
        self.assertEqual(len(self.seen), 1)

    def test_invalid_route_never_spends(self):
        for body in (
            request(model="another-model"), request(stream=True), request(max_tokens=0),
            request(max_tokens=9000), request(temperature=0.4),
            json.dumps({"model":MODEL,"messages":[{"role":"user","content":[{"type":"image_url","image_url":"x"}]}],
                        "max_completion_tokens":12}).encode(),
        ):
            with self.subTest(body=body[:80]), self.assertRaises(ReceiptError):
                self.gateway.handle(body, "invalid")
        self.assertEqual(self.seen, [])
        self.assertEqual(self.ledger.entries(), [])

    def test_tool_calls_and_tools_accepted(self):
        payload = {"model": MODEL, "messages": [
            {"role":"assistant","content":None,"tool_calls":[{"id":"call-1","type":"function",
                "function":{"name":"check","arguments":"{}"}}]},
            {"role":"tool","tool_call_id":"call-1","content":"ok"}],
            "max_completion_tokens":20,
            "tools":[{"type":"function","function":{"name":"check","description":"check","parameters":{"type":"object"}}}],
            "tool_choice":"auto"}
        self.gateway.transport = lambda _body, _key: success(prompt=100, completion=12)
        self.gateway.handle(json.dumps(payload).encode(), "call-with-tools")
        self.assertEqual(self.ledger.snapshot().settled, "0.00248")

    def test_ambiguous_timeout_is_not_released(self):
        def timeout(_body, _key):
            raise TimeoutError("mock timeout")
        self.gateway.transport = timeout
        with self.assertRaises(TimeoutError):
            self.gateway.handle(request(), "uncertain")
        self.assertEqual(self.ledger.snapshot().uncertain, 1)
        self.assertNotEqual(self.ledger.snapshot().reserved, "0")
        self.assertEqual(self.ledger.entries()[0]["actual_usd"], None)

    def test_unknown_usage_and_error_http_stay_reserved(self):
        for i, response in enumerate((UpstreamResponse(429, b'{"error":"rate limit"}'),
                                      UpstreamResponse(200, b'{"model":"test-model-1","choices":[]}'))):
            self.gateway.transport = lambda _body, _key, response=response: response
            if i == 0:
                status, _ = self.gateway.handle(request(), "rate-limited")
                self.assertEqual(status, 502)
            else:
                with self.assertRaisesRegex(ReceiptError, "omitted usage"):
                    self.gateway.handle(request(), "no-usage")
        self.assertEqual(self.ledger.snapshot().uncertain, 2)

    def test_exceeding_reserved_response_usage_is_uncertain(self):
        self.gateway.transport = lambda _body, _key: success(prompt=100, completion=101)
        with self.assertRaisesRegex(ReceiptError, "above reserved"):
            self.gateway.handle(request(max_tokens=100), "overrun")
        self.assertEqual(self.ledger.snapshot().uncertain, 1)

    def test_concurrent_requests_have_atomic_admission(self):
        constrained = BudgetLedger(self.root / "tiny.db", budget_usd="0.017")
        started = threading.Event()
        release = threading.Event()
        def slow(_body, _key):
            started.set()
            if not release.wait(timeout=5):
                raise TimeoutError("test synchronization failed")
            return success()
        gw = Gateway(constrained, self.price, client_token=TOKEN, provider_key=SECRET,
                     transport=slow)
        def one(i):
            try:
                gw.handle(request(), f"concurrent-{i}")
                return True
            except ReceiptError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            first = pool.submit(one, 0)
            self.assertTrue(started.wait(timeout=5))
            others = [pool.submit(one, i) for i in range(1, 12)]
            self.assertEqual(sum(job.result(timeout=5) for job in others), 0)
            release.set()
            self.assertTrue(first.result(timeout=5))
        self.assertEqual(len(constrained.entries()), 1)
        self.assertEqual(constrained.snapshot().settled, "0.0036")

    def test_local_http_credentials_and_bounds(self):
        server = _LocalServer(("127.0.0.1", 0), self.gateway)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def send(path, token=None, data=None, headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            try:
                h = {"Content-Type":"application/json"}
                if token is not None:
                    h["Authorization"] = "Bearer " + token
                if headers:
                    h.update(headers)
                conn.request("POST", path, body=data or request(), headers=h)
                reply = conn.getresponse()
                return reply.status, reply.read()
            finally:
                conn.close()
        status, _ = send("/v1/chat/completions", token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(len(self.seen), 0)
        status, _ = send("/v1/unknown", token=TOKEN)
        self.assertEqual(status, 404)
        self.assertEqual(len(self.seen), 0)
        status, raw = send("/v1/chat/completions", token=TOKEN, headers={"X-Cost-To-Done-Request-Id":"http-001"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.seen), 1)
        status, raw = send("/v1/chat/completions", token=TOKEN, headers={"X-Cost-To-Done-Request-Id":"http-001"})
        self.assertEqual(status, 400)
        self.assertEqual(len(self.seen), 1)

    def test_schedule_identity_immutable_even_after_restart(self):
        old = self.ledger.snapshot()
        self.assertEqual(old.schedule_sha256, self.price.digest)
        reopened = BudgetLedger(self.root / "ledger.sqlite3", budget_usd="0.1")
        self.assertEqual(reopened.snapshot().schedule_sha256, self.price.digest)
        changed = PriceSchedule(MODEL, "2026-11-21", "https://example.com/price-source", "21", "40")
        with self.assertRaisesRegex(ReceiptError, "price schedule differs"):
            Gateway(reopened, changed, client_token=TOKEN, provider_key=SECRET,
                    transport=lambda _b, _k: success())
        self.assertEqual(reopened.snapshot().schedule_sha256, self.price.digest)

    def test_no_retroactive_price_attachment(self):
        old = BudgetLedger(self.root / "old-ledger.db", budget_usd="1")
        old.reserve("trial-1", "0.1")
        with self.assertRaisesRegex(ReceiptError, "after spending began"):
            old.bind_schedule(self.price.digest)

    def test_upstream_secret_and_prompts_absent_from_ledger(self):
        self.gateway.handle(request(), "secret-check")
        contents = (self.root / "ledger.sqlite3").read_bytes()
        self.assertNotIn(SECRET.encode(), contents)
        self.assertNotIn(TOKEN.encode(), contents)
        self.assertNotIn(b"Fix the issue", contents)
        self.assertEqual(self.ledger.snapshot().schedule_sha256, self.price.digest)

    def test_schedule_source_and_digest(self):
        self.assertEqual(self.price.digest, self.price.digest)
        for val in ("-1", "NaN", "1e-8", "0.0000000000001"):
            with self.subTest(val=val):
                bad = PriceSchedule(MODEL, "2026-11-20", "https://example.com/pricing", val, "40")
                with self.assertRaises(ReceiptError):
                    bad.validate()
        with self.assertRaises(ReceiptError):
            PriceSchedule(MODEL, "2026-02-30", "https://example.com", "1", "1").validate()


    def test_responses_only_model_tool_calls_fail_before_budget_and_network(self):
        tools = [{"type": "function", "function": {
            "name": "bash", "parameters": {"type": "object"}}}]
        for model in ("gpt-6.1-terra", "gpt-6.2-sol", "gpt-6.2-astra",
                      "gpt-6.1-terra-2026-11-01"):
            with self.subTest(model=model):
                self.gateway.price = PriceSchedule(
                    model, "2026-11-23", "https://example.com/prices", "2", "10")
                before = self.ledger.entries()
                with self.assertRaisesRegex(ReceiptError, "Responses API"):
                    self.gateway.handle(request(model=model, tools=tools), "unsupported")
                self.assertEqual(before, self.ledger.entries())
        self.assertEqual(self.seen, [])

    def test_chat_function_tools_explicitly_disable_reasoning_on_gpt54(self):
        model = "gpt-5.4-mini"
        self.gateway.price = PriceSchedule(
            model, "2026-11-23", "https://example.com/prices", "0.75", "4.5")
        self.gateway.transport = lambda body, key: (
            self.seen.append(json.loads(body)) or success(
                prompt=100, completion=4, model=model))
        body = request(model=model, tools=[{"type":"function","function":{
            "name":"bash","parameters":{"type":"object"}}}])
        status, _ = self.gateway.handle(body, "gpt54-tools")
        self.assertEqual(status, 200)
        self.assertEqual(self.seen[0]["reasoning_effort"], "none")
        self.assertEqual(self.ledger.snapshot().uncertain, 0)
        with self.assertRaisesRegex(ReceiptError, "reasoning_effort"):
            self.gateway.handle(request(model=model, tools=[
                {"type":"function","function":{"name":"bash",
                 "parameters":{"type":"object"}}}],
                reasoning_effort="medium"), "should-reject")
        self.assertEqual(len(self.seen), 1)

if __name__ == "__main__":
    unittest.main()
