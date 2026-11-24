"""Restricted, stateless OpenAI Responses request and usage contract.

This is a non-streaming protocol subset for local function tools. It does
not authenticate provider billing or validate the task's acceptance tests.
"""
from __future__ import annotations

import json
from typing import Any

from .core import ReceiptError

ROUTE = "/v1/responses"
_ALLOWED = frozenset({
    "model", "input", "instructions", "max_output_tokens", "store", "stream",
    "tools", "tool_choice", "parallel_tool_calls", "reasoning", "include",
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
    _require(obj.get("stream", False) is False, "Responses streaming not supported")
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
    _require(obj.get("tool_choice", "auto") in ("auto", "none", "required"),
             "unsupported Responses tool_choice")
    _require(type(obj.get("parallel_tool_calls", False)) is bool,
             "parallel_tool_calls must be boolean")
    if "reasoning" in obj:
        reason = obj["reasoning"]
        _require(_fields(reason, {"effort"}) and reason.get("effort") in
                 ("none", "minimal", "low", "medium", "high", "xhigh"),
                 "unsupported reasoning settings")
    _require(obj.get("include", []) in ([], ["reasoning.encrypted_content"]),
             "unsupported Responses include fields")
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
