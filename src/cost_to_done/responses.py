"""Restricted, stateless OpenAI Responses request and usage contract.

This is a buffered HTTP protocol subset for local function tools. It does
not authenticate provider billing or validate the task's acceptance tests.
"""
from __future__ import annotations

import json
from typing import Any

from .core import ReceiptError

ROUTE = "/v1/responses"
_ALLOWED = frozenset({
    "model", "input", "instructions", "max_output_tokens", "store", "stream",
    "tools", "tool_choice", "parallel_tool_calls", "reasoning", "include", "prompt_cache_key",
})


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ReceiptError(message)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


def _bad_constant(_: str) -> Any:
    raise ValueError("nonfinite JSON")


def _decode(data: bytes) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=_bad_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReceiptError("invalid Responses JSON") from exc


def _fields(item: Any, allowed: set[str]) -> bool:
    return isinstance(item, dict) and set(item) <= allowed


def _string(value: Any) -> bool:
    return isinstance(value, str)


def _text_parts(value: Any, role: str) -> bool:
    if _string(value):
        return True
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        return False
    for part in value:
        if not isinstance(part, dict):
            return False
        if role == "assistant" and part.get("type") == "refusal":
            if set(part) != {"type", "refusal"} or not _string(part["refusal"]):
                return False
        elif role == "assistant" and part.get("type") == "output_text":
            if (not _fields(part, {"type", "text", "annotations", "logprobs"})
                    or not _string(part.get("text"))
                    or part.get("annotations", []) != []
                    or part.get("logprobs", []) != []):
                return False
        elif (set(part) != {"type", "text"} or part.get("type") != "input_text"
              or not _string(part.get("text"))):
            return False
    return True


def _validate_item(item: Any) -> None:
    _require(isinstance(item, dict), "Responses input item must be an object")
    kind = item.get("type", "message")
    if kind == "message":
        role = item.get("role")
        _require(_fields(item, {"type", "role", "content", "id", "status"})
                 and role in ("system", "developer", "user", "assistant")
                 and _text_parts(item.get("content"), role),
                 "unsupported Responses message")
    elif kind == "function_call":
        _require(_fields(item, {"type", "id", "call_id", "name", "arguments", "status"})
                 and all(_string(item.get(k)) for k in ("call_id", "name", "arguments")),
                 "unsupported Responses function call")
    elif kind == "function_call_output":
        _require(_fields(item, {"type", "id", "call_id", "output", "status"})
                 and all(_string(item.get(k)) for k in ("call_id", "output")),
                 "unsupported Responses function output")
    elif kind == "reasoning":
        _require(_fields(item, {"type", "id", "summary", "encrypted_content", "status"})
                 and _string(item.get("id"))
                 and _string(item.get("encrypted_content"))
                 and bool(item["encrypted_content"]),
                 "stateless reasoning item needs encrypted content")
        summary = item.get("summary")
        _require(isinstance(summary, list) and all(
            isinstance(part, dict) and set(part) == {"type", "text"}
            and part["type"] == "summary_text" and _string(part["text"])
            for part in summary), "invalid reasoning summary")
    else:
        raise ReceiptError("unsupported Responses input item type")
    for key in ("id", "status"):
        _require(key not in item or _string(item[key]), "invalid item metadata")


def bounded_request(data: bytes, *, model: str, max_output_cap: int,
                    max_request_bytes: int) -> tuple[dict[str, Any], int]:
    """Return a normalized request and heuristic input-token envelope."""
    _require(0 < len(data) <= max_request_bytes, "invalid Responses request size")
    obj = _decode(data)
    _require(isinstance(obj, dict) and set(obj) <= _ALLOWED,
             "unsupported Responses request fields")
    _require(obj.get("model") == model, "model must exactly match priced route")
    _require(obj.get("store", False) is False, "Responses store must be false")
    _require(type(obj.get("stream", False)) is bool, "stream must be a JSON boolean")
    cap = obj.get("max_output_tokens")
    _require(type(cap) is int and 1 <= cap <= max_output_cap,
             "explicit bounded max_output_tokens is required")
    items = obj.get("input")
    if isinstance(items, str):
        count = 1
    else:
        _require(isinstance(items, list) and 1 <= len(items) <= 100,
                 "Responses input must be text or a bounded item list")
        count = len(items)
        for item in items:
            _validate_item(item)
    if "instructions" in obj:
        _require(_string(obj["instructions"]), "instructions must be text")
    tools = obj.get("tools", [])
    _require(isinstance(tools, list) and len(tools) <= 64, "tools must be bounded")
    names: set[str] = set()
    for tool in tools:
        _require(_fields(tool, {"type", "name", "description", "parameters", "strict"})
                 and tool.get("type") == "function"
                 and _string(tool.get("name")) and bool(tool["name"])
                 and isinstance(tool.get("parameters"), dict)
                 and ("description" not in tool or _string(tool["description"]))
                 and ("strict" not in tool or type(tool["strict"]) is bool),
                 "only local JSON function tools supported")
        _require(tool["name"] not in names, "duplicate function name")
        names.add(tool["name"])
        # Pi schemas have optional fields. Preserve non-strict semantics.
        tool.setdefault("strict", False)
    _require(obj.get("tool_choice", "auto") in ("auto", "none", "required"),
             "unsupported Responses tool_choice")
    _require(type(obj.get("parallel_tool_calls", False)) is bool,
             "parallel_tool_calls must be boolean")
    if "reasoning" in obj:
        reason = obj["reasoning"]
        _require(_fields(reason, {"effort", "summary"}) and reason.get("summary", "auto") in
                 ("auto", "concise", "detailed") and reason.get("effort") in
                 ("none", "minimal", "low", "medium", "high", "xhigh"),
                 "unsupported reasoning settings")
    _require(obj.get("include", []) in ([], ["reasoning.encrypted_content"]),
             "unsupported Responses include fields")
    # Drop Pi session cache-routing identifiers; use undiscounted input rates.
    if "prompt_cache_key" in obj:
        key = obj.pop("prompt_cache_key")
        _require(isinstance(key, str) and 0 < len(key) <= 128,
                 "invalid prompt_cache_key")
    # Explicitly disable stored conversation state and request replayable reasoning.
    obj["store"] = False
    obj["include"] = ["reasoning.encrypted_content"]
    try:
        normalized = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ReceiptError("unserializable Responses request") from exc
    _require(len(normalized) <= max_request_bytes, "normalized request too large")
    return obj, 4 * max(len(data), len(normalized)) + 32 * count + 64


def token_usage(payload: bytes, model: str) -> tuple[int, int]:
    """Read terminal usage, including incomplete but metered responses."""
    obj = _decode(payload)
    _require(isinstance(obj, dict) and obj.get("object") == "response"
             and obj.get("model") == model
             and obj.get("status") in ("completed", "incomplete"),
             "nonterminal or mismatched Responses result; charge uncertain")
    usage = obj.get("usage")
    _require(isinstance(usage, dict), "missing Responses usage; charge uncertain")
    inputs, outputs, total = (usage.get(k) for k in
                              ("input_tokens", "output_tokens", "total_tokens"))
    _require(all(type(n) is int and n >= 0 for n in (inputs, outputs, total))
             and inputs + outputs == total,
             "invalid Responses usage; charge uncertain")
    return inputs, outputs


# The HTTP Responses stream uses typed JSON SSE events, not Chat Completions'
# [DONE] sentinel. Restrict lifecycle events to one response identity.
_TERMINAL = {"response.completed": "completed", "response.incomplete": "incomplete"}
_LIFECYCLE = {"response.created", "response.in_progress", *_TERMINAL}
_ALLOWED_EVENTS = _LIFECYCLE | {
    "response.output_item.added", "response.output_item.done",
    "response.content_part.added", "response.content_part.done",
    "response.output_text.delta", "response.output_text.done",
    "response.refusal.delta", "response.refusal.done",
    "response.function_call_arguments.delta", "response.function_call_arguments.done",
    "response.reasoning_summary_part.added", "response.reasoning_summary_part.done",
    "response.reasoning_summary_text.delta", "response.reasoning_summary_text.done",
    "response.reasoning_text.delta", "response.reasoning_text.done",
}


def _sse_frames(payload: bytes):
    """Yield named data frames; reject unsupported or unterminated framing."""
    try:
        source = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ReceiptError("Responses SSE is not UTF-8") from exc
    source = source.replace("\r\n", "\n")
    _require("\r" not in source and source.endswith("\n\n"),
             "truncated or unsupported Responses SSE framing")
    name: str | None = None
    data: list[str] = []
    for line in source.split("\n"):
        if line == "":
            if name is not None or data:
                _require(bool(data), "SSE event missing data")
                yield name, "\n".join(data)
                name, data = None, []
        elif line.startswith(":"):
            continue
        else:
            field, sep, value = line.partition(":")
            _require(bool(sep), "unsupported Responses SSE field")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                _require(name is None and bool(value), "invalid SSE event name")
                name = value
            elif field == "data":
                data.append(value)
            else:
                raise ReceiptError("unsupported Responses SSE field")


def stream_token_usage(payload: bytes, model: str) -> tuple[int, int]:
    """Require one complete, ordered response with terminal metered usage.

    This parser validates the accounting boundary, not the semantic content
    of every tool argument or token delta. It fails closed on unrecognized
    event types, failed responses, truncated streams and inconsistent usage.
    """
    identity: str | None = None
    last_sequence: int | None = None
    terminal: tuple[int, int] | None = None
    for name, data in _sse_frames(payload):
        _require(terminal is None, "event after terminal Responses result")
        event = _decode(data.encode("utf-8"))
        _require(isinstance(event, dict), "invalid Responses SSE event")
        kind = event.get("type")
        _require(isinstance(kind, str) and kind in _ALLOWED_EVENTS,
                 "unsupported or failed Responses SSE event")
        _require(name is None or name == kind, "SSE name/type mismatch")
        seq = event.get("sequence_number")
        _require(type(seq) is int and seq >= 0
                 and (last_sequence is None or seq == last_sequence + 1),
                 "noncontiguous Responses SSE sequence")
        last_sequence = seq
        if identity is None:
            _require(kind == "response.created", "missing initial response.created")
        else:
            _require(kind != "response.created", "duplicate response.created")
        if kind in _LIFECYCLE:
            raw = event.get("response")
            _require(isinstance(raw, dict) and raw.get("object") == "response"
                     and raw.get("model") == model
                     and isinstance(raw.get("id"), str) and bool(raw["id"]),
                     "invalid Responses lifecycle identity")
            if identity is None:
                identity = raw["id"]
            _require(raw["id"] == identity, "Responses lifecycle identity changed")
            if kind in _TERMINAL:
                _require(raw.get("status") == _TERMINAL[kind],
                         "Responses terminal status mismatch")
                terminal = token_usage(json.dumps(raw).encode("utf-8"), model)
            else:
                _require(raw.get("status") in ("queued", "in_progress")
                         and raw.get("usage") is None,
                         "invalid nonterminal Responses lifecycle")
        if "response_id" in event:
            _require(event["response_id"] == identity, "Responses event identity mismatch")
    _require(terminal is not None, "missing terminal Responses usage")
    return terminal
