"""Conservative, narrowly scoped inference-admission gateway.

This module supports a constrained OpenAI Chat Completions route, including
fully buffered streaming responses with verifiable terminal usage. It
checks a pessimistic *estimate* before forwarding and retains reservations on
ambiguous failures. It is NOT a hard cap on provider invoices: model tokenizer,
provider-specific charges, cancelled requests, and upstream noncompliance are
outside the verified boundary. Keep provider credentials outside the agent.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import ssl
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from .core import ReceiptError
from .ledger import BudgetLedger, _usd, _units

MAX_REQUEST_BYTES = 256_000
MAX_RESPONSE_BYTES = 4_000_000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_RATE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_ROUTE = "/v1/chat/completions"
_UPSTREAM = "api.openai.com"
_ALLOWED_TOP = frozenset({"model", "messages", "max_completion_tokens", "stream", "stream_options", "store", "tools", "tool_choice"})
_ALLOWED_MESSAGE = frozenset({"role", "content", "tool_calls", "tool_call_id", "name", "refusal"})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _dec(value: str) -> Decimal:
    if not isinstance(value, str) or _RATE.fullmatch(value) is None:
        raise ReceiptError("rate must be an exact, nonnegative decimal string (up to 12 places)")
    number = Decimal(value)
    if number > 100_000:
        raise ReceiptError("rate above accepted operational range")
    return number


@dataclass(frozen=True)
class PriceSchedule:
    """Operator-pinned per-million-token rates, not validated provider prices."""

    model: str
    effective_date: str
    source_url: str
    input_per_million_usd: str
    output_per_million_usd: str

    @classmethod
    def load(cls, path: Path) -> "PriceSchedule":
        """Read an immutable-identity price declaration from a local JSON file."""
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            raise ReceiptError("price schedule must be a small regular JSON file")
        obj = json.loads(path.read_text(encoding="utf-8"))
        fields = set(cls.__dataclass_fields__)
        if not isinstance(obj, dict) or set(obj) != fields:
            raise ReceiptError("price schedule has missing or unknown fields")
        out = cls(**obj)
        out.validate()
        return out

    def validate(self) -> None:
        if (not isinstance(self.model, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,120}", self.model)):
            raise ReceiptError("invalid priced model identifier")
        if not isinstance(self.effective_date, str) or not _DATE.fullmatch(self.effective_date):
            raise ReceiptError("effective_date must be YYYY-MM-DD")
        from datetime import date
        try:
            date.fromisoformat(self.effective_date)
        except ValueError as exc:
            raise ReceiptError("invalid calendar effective_date") from exc
        url = urlsplit(self.source_url) if isinstance(self.source_url, str) else None
        if not url or url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ReceiptError("price source must be an HTTPS URL")
        _dec(self.input_per_million_usd)
        _dec(self.output_per_million_usd)

    @property
    def digest(self) -> str:
        self.validate()
        return hashlib.sha256(_canonical(vars(self))).hexdigest()


def _bounded_request(data: bytes, *, model: str) -> tuple[dict[str, Any], int]:
    """Accept just one costed route; reject opaque/multimodal and unbounded calls.

    Byte length is a *heuristic token envelope*, not a tokenizer guarantee.
    Pricing and provider compliance are additional unverified assumptions.
    """
    if len(data) == 0 or len(data) > MAX_REQUEST_BYTES:
        raise ReceiptError("request exceeds bounded nonempty request size")
    try:
        obj = json.loads(data.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise ReceiptError("invalid JSON request") from exc
    if not isinstance(obj, dict) or not set(obj).issubset(_ALLOWED_TOP):
        raise ReceiptError("unsupported Chat Completions request fields")
    if obj.get("model") != model:
        raise ReceiptError("model must exactly match priced route")
    if type(obj.get("stream", False)) is not bool:
        raise ReceiptError("stream must be a JSON boolean")
    streaming = obj.get("stream", False)
    if obj.get("store", False) is not False:
        raise ReceiptError("store must be false; persisted provider requests are unsupported")
    options = obj.get("stream_options")
    if streaming:
        if options != {"include_usage": True}:
            raise ReceiptError("streaming requires stream_options.include_usage=true")
    elif options is not None:
        raise ReceiptError("stream_options without streaming is unsupported")
    cap = obj.get("max_completion_tokens")
    if type(cap) is not int or not 1 <= cap <= 4096:
        raise ReceiptError("explicit max_completion_tokens in [1,4096] is required")
    messages = obj.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise ReceiptError("messages must be a nonempty bounded list")
    for msg in messages:
        if not isinstance(msg, dict) or not set(msg).issubset(_ALLOWED_MESSAGE):
            raise ReceiptError("unsupported message fields")
        if msg.get("role") not in ("system", "developer", "user", "assistant", "tool"):
            raise ReceiptError("unsupported message role")
        if not (isinstance(msg.get("content"), str) or
                (msg.get("content") is None and msg.get("role") == "assistant" and isinstance(msg.get("tool_calls"), list))):
            raise ReceiptError("only textual message content or assistant tool calls supported")
        for key in ("name", "tool_call_id", "refusal"):
            if key in msg and msg[key] is not None and not isinstance(msg[key], str):
                raise ReceiptError("invalid message metadata")
        if "tool_calls" in msg:
            calls = msg["tool_calls"]
            if msg["role"] != "assistant" or not isinstance(calls, list) or len(calls) > 32:
                raise ReceiptError("invalid tool calls")
            for call in calls:
                if not isinstance(call, dict) or set(call) != {"id", "type", "function"} or call["type"] != "function":
                    raise ReceiptError("invalid tool call representation")
                fun = call["function"]
                if (not isinstance(call["id"], str) or not isinstance(fun, dict) or
                        set(fun) != {"name", "arguments"} or
                        not isinstance(fun["name"], str) or not isinstance(fun["arguments"], str)):
                    raise ReceiptError("invalid function call")
    tools = obj.get("tools", [])
    if not isinstance(tools, list) or len(tools) > 64:
        raise ReceiptError("tools must be bounded")
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {"type", "function"} or tool["type"] != "function":
            raise ReceiptError("only JSON function tools are supported")
        fun = tool["function"]
        if (not isinstance(fun, dict) or not isinstance(fun.get("name"), str)
                or not isinstance(fun.get("parameters"), dict)
                or set(fun).difference({"name", "description", "parameters", "strict"})):
            raise ReceiptError("unsupported function declaration")
    if "tool_choice" in obj and obj["tool_choice"] not in ("none", "auto", "required"):
        raise ReceiptError("unsupported tool_choice")
    # The envelope includes every UTF-8 byte in the API request four times
    # plus a per-message allowance. It is intentionally not described as a
    # formal upper bound for provider-side prompt tokenization.
    token_envelope = 4 * len(data) + 32 * len(messages) + 64
    return obj, token_envelope


def _money_estimate(tokens: int, per_million: Decimal) -> int:
    units = (Decimal(tokens) * per_million * Decimal(10**12) / Decimal(1_000_000)).to_integral_value(rounding=ROUND_CEILING)
    return int(units)


@dataclass(frozen=True)
class UpstreamResponse:
    status: int
    body: bytes
    content_type: str = "application/json"


Transport = Callable[[bytes, str], UpstreamResponse]


def openai_transport(body: bytes, api_key: str) -> UpstreamResponse:
    """Send one non-redirectable HTTPS request to the fixed provider host."""
    conn = http.client.HTTPSConnection(_UPSTREAM, timeout=90, context=ssl.create_default_context())
    try:
        conn.request("POST", _ROUTE, body=body, headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "cost-to-done-gateway/0.1",
        })
        response = conn.getresponse()
        content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ReceiptError("upstream response size exceeded; usage uncertain")
        return UpstreamResponse(response.status, content,
                                response.getheader("Content-Type", "application/octet-stream"))
    finally:
        conn.close()


def _stream_token_usage(payload: bytes, model: str) -> tuple[int, int]:
    """Parse a fully buffered OpenAI SSE completion, refusing incomplete usage.

    The original stream is forwarded byte-for-byte *only after* validation and
    settlement. This intentionally sacrifices incremental output to keep
    completion/accounting consistent with the durable reservation.
    """
    try:
        source = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ReceiptError("stream is not valid UTF-8") from exc
    if not source.endswith(("\n\n", "\r\n\r\n")):
        raise ReceiptError("truncated terminal stream framing")
    frames: list[str] = []
    current: list[str] = []
    for raw_line in source.splitlines():
        if not raw_line:
            if current:
                frames.append("\n".join(current))
                current = []
            continue
        if raw_line.startswith(":"):
            continue  # Valid SSE comment, never interpreted as usage.
        if not raw_line.startswith("data: "):
            raise ReceiptError("unsupported SSE event field")
        current.append(raw_line[6:])
    if current:
        raise ReceiptError("unterminated SSE event")
    if not frames or frames[-1] != "[DONE]" or frames.count("[DONE]") != 1:
        raise ReceiptError("stream lacks an unambiguous final [DONE] marker")
    if len(frames) < 3:
        raise ReceiptError("stream is missing completion or usage events")
    usage: tuple[int, int] | None = None
    saw_final_choice = False
    for event_index, raw in enumerate(frames[:-1]):
        try:
            event = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ReceiptError("invalid JSON stream event") from exc
        if not isinstance(event, dict) or event.get("model") != model:
            raise ReceiptError("stream event model mismatch")
        choices = event.get("choices")
        if not isinstance(choices, list):
            raise ReceiptError("stream event lacks choices")
        if event.get("usage") is not None:
            if usage is not None or choices or event_index != len(frames) - 2:
                raise ReceiptError("usage must appear once in the final data event")
            reported = event["usage"]
            if not isinstance(reported, dict):
                raise ReceiptError("invalid terminal stream usage")
            prompt = reported.get("prompt_tokens")
            completion = reported.get("completion_tokens")
            if type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0:
                raise ReceiptError("invalid terminal stream token counts")
            usage = (prompt, completion)
        elif choices:
            for choice in choices:
                if not isinstance(choice, dict):
                    raise ReceiptError("invalid streamed choice")
                finish = choice.get("finish_reason")
                if finish is not None:
                    if finish not in ("stop", "length", "tool_calls", "content_filter", "function_call"):
                        raise ReceiptError("unsupported stream finish reason")
                    saw_final_choice = True
        else:
            raise ReceiptError("empty stream event without terminal usage")
    if usage is None or not saw_final_choice:
        raise ReceiptError("stream lacks finish reason or complete terminal usage")
    return usage


class Gateway:
    """Local authenticated request broker backed by a durable budget ledger.

    `transport` injection is for deterministic tests. In production, only the
    fixed HTTPS upstream transport is selected. Client request headers never
    reach the provider. Even a successful response is priced as an *estimate*.
    """

    def __init__(self, ledger: BudgetLedger, price: PriceSchedule, *, client_token: str,
                 provider_key: str, transport: Transport = openai_transport):
        price.validate()
        if not isinstance(client_token, str) or len(client_token) < 24:
            raise ReceiptError("gateway client token must have at least 24 characters")
        if not isinstance(provider_key, str) or not provider_key:
            raise ReceiptError("provider credential missing")
        if hmac.compare_digest(client_token, provider_key):
            raise ReceiptError("provider and gateway credentials must be different")
        ledger.bind_schedule(price.digest)
        self.ledger = ledger
        self.price = price
        self.client_token = client_token
        self.provider_key = provider_key
        self.transport = transport

    def authorize(self, bearer: str | None) -> bool:
        return (isinstance(bearer, str) and bearer.startswith("Bearer ")
                and hmac.compare_digest(bearer[7:], self.client_token))

    def handle(self, data: bytes, request_id: str) -> tuple[int, bytes]:
        """Preauthorize, forward once, settle or retain uncertain reservation."""
        if not _ID.fullmatch(request_id):
            raise ReceiptError("invalid request ID")
        obj, input_envelope = _bounded_request(data, model=self.price.model)
        bound_units = (_money_estimate(input_envelope, _dec(self.price.input_per_million_usd))
                       + _money_estimate(obj["max_completion_tokens"], _dec(self.price.output_per_million_usd)))
        if bound_units <= 0:
            raise ReceiptError("zero-priced routes are not supported by this gateway")
        if bound_units > 100_000 * 10**12:
            raise ReceiptError("per-request price exceeds supported ledger amount")
        self.ledger.reserve(request_id, _usd(bound_units))
        try:
            response = self.transport(_canonical(obj), self.provider_key)
            if not isinstance(response, UpstreamResponse) or len(response.body) > MAX_RESPONSE_BYTES:
                raise ReceiptError("upstream result is invalid; reservation retained")
            # HTTP errors are never assumed to be free. They are ambiguous until
            # provider telemetry independently confirms a zero or nonzero bill.
            if response.status != 200:
                self.ledger.mark_uncertain(request_id)
                return 502, _canonical({"error": "upstream request failed; charge uncertain", "request_id": request_id})
            mime = response.content_type.split(";", 1)[0].strip().lower()
            if obj.get("stream", False):
                if mime != "text/event-stream":
                    raise ReceiptError("streaming response content type mismatch; charge uncertain")
                prompt, completion = _stream_token_usage(response.body, self.price.model)
            else:
                if mime != "application/json":
                    raise ReceiptError("JSON response content type mismatch; charge uncertain")
                raw = json.loads(response.body.decode("utf-8"))
                if not isinstance(raw, dict) or raw.get("model") != self.price.model:
                    raise ReceiptError("provider response model mismatch; charge uncertain")
                usage = raw.get("usage")
                if not isinstance(usage, dict):
                    raise ReceiptError("provider omitted usage; charge uncertain")
                prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0:
                    raise ReceiptError("invalid usage fields; charge uncertain")
            if prompt > input_envelope or completion > obj["max_completion_tokens"]:
                raise ReceiptError("provider reported usage above reserved envelope; charge uncertain")
            estimated = (_money_estimate(prompt, _dec(self.price.input_per_million_usd))
                         + _money_estimate(completion, _dec(self.price.output_per_million_usd)))
            self.ledger.settle(request_id, _usd(estimated))
            return 200, response.body
        except Exception:
            # Conservative on transport failure, timeout, malformed response or
            # process interruption, without ever discarding possible spend.
            try:
                self.ledger.mark_uncertain(request_id)
            except ReceiptError:
                pass
            raise


class _LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], gateway: Gateway):
        self.gateway = gateway
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _LocalServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logs: URLs and headers might contain secrets."""

    def _reply(self, code: int, payload: bytes, *, content_type: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def do_POST(self) -> None:
        gw = self.server.gateway
        if self.path != _ROUTE:
            self._reply(404, b'{"error":"route not supported"}')
            return
        if not gw.authorize(self.headers.get("Authorization")):
            self._reply(401, b'{"error":"unauthorized"}')
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._reply(400, b'{"error":"transfer encodings unsupported"}')
            return
        if len(self.headers.get_all("Authorization", [])) != 1:
            self._reply(400, b'{"error":"duplicate authorization headers"}')
            return
        if len(self.headers.get_all("Content-Length", [])) != 1:
            self._reply(400, b'{"error":"one Content-Length header required"}')
            return
        try:
            length = int(self.headers["Content-Length"])
        except (ValueError, TypeError):
            self._reply(400, b'{"error":"invalid Content-Length"}')
            return
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._reply(413, b'{"error":"request body limit exceeded"}')
            return
        data = self.rfile.read(length)
        if len(data) != length:
            self._reply(400, b'{"error":"truncated request body"}')
            return
        request_id = self.headers.get("X-Cost-To-Done-Request-Id") or secrets.token_hex(16)
        try:
            status, content = gw.handle(data, request_id)
        except ReceiptError as exc:
            message = str(exc)
            status = 402 if "admission denied" in message else 400
            # No credential or upstream response is written to client errors.
            content = _canonical({"error": message, "request_id": request_id})
        except Exception:
            status, content = 502, _canonical({"error": "provider outcome uncertain", "request_id": request_id})
        content_type = "text/event-stream" if status == 200 and content.startswith(b"data: ") else "application/json"
        self._reply(status, content, content_type=content_type)

    def do_GET(self) -> None:
        self._reply(404, b'{"error":"route not supported"}')


def serve_local(*, ledger_path: Path, budget_usd: str, price_path: Path,
                port: int, gateway_token: str, provider_key: str) -> None:
    """Serve on IPv4 loopback only. Network egress isolation is external."""
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ReceiptError("gateway port must be in [1024, 65535]")
    price = PriceSchedule.load(price_path)
    ledger = BudgetLedger(ledger_path, budget_usd=budget_usd)
    gateway = Gateway(ledger, price, client_token=gateway_token, provider_key=provider_key)
    with _LocalServer(("127.0.0.1", port), gateway) as httpd:
        print(f"Cost to Done gateway listening on 127.0.0.1:{port}; price_sha256={price.digest}", flush=True)
        httpd.serve_forever(poll_interval=0.2)
