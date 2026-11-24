"""Deterministic mock coding response for Harbor's *protocol* acceptance test.

This fixture is a synthetic scripted repair, not an AI-generated result. It lives
only in the fake provider container. The evaluated Harbor task container does
not receive this source or the oracle solution.
"""
from __future__ import annotations

import json

REPAIR_SOURCE = '''"""Exact integer proportional allocation with index-stable remainder ties."""


def allocate_cents(total_cents: int, weights: list[int]) -> list[int]:
    """Allocate a nonnegative integer exactly using largest remainders."""
    if type(total_cents) is not int or total_cents < 0:
        raise ValueError("total_cents must be a nonnegative integer")
    if not isinstance(weights, list) or not weights:
        raise ValueError("weights must be a nonempty list")
    if any(type(w) is not int or w < 0 for w in weights):
        raise ValueError("weights must be nonnegative integers")
    denominator = sum(weights)
    if denominator == 0:
        raise ValueError("at least one weight must be positive")
    allocations = []
    remainders = []
    for weight in weights:
        share, remainder = divmod(total_cents * weight, denominator)
        allocations.append(share)
        remainders.append(remainder)
    additional = total_cents - sum(allocations)
    ordered = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for index in ordered[:additional]:
        allocations[index] += 1
    return allocations
'''

CALL_ID = "ctd-scripted-repair-1"


def scripted_reply(request: dict) -> tuple[dict, str]:
    """Return a tool call, then a final reply once the tool result appears.

    Only tool names advertised by the agent are used. The second invocation
    proves that the agent transmitted the tool result, not just a repeated
    first-turn prompt. Real model behavior is intentionally not simulated.
    """
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("scripted repair needs a nonempty message history")

    if any(isinstance(msg, dict) and msg.get("role") == "tool" for msg in messages):
        tool_results = [msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "tool"]
        if len(tool_results) != 1 or tool_results[0].get("tool_call_id") != CALL_ID:
            raise ValueError("second request must contain the scripted repair tool result")
        return {"content": "The requested source change has been applied."}, "stop"

    declared = {
        tool.get("function", {}).get("name")
        for tool in request.get("tools", [])
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict)
    }
    if "write" in declared:
        name = "write"
        args = {"path": "/app/allocate.py", "content": REPAIR_SOURCE}
    elif "bash" in declared:
        name = "bash"
        args = {"command": "cat > /app/allocate.py <<'CTD_MOCK_SOURCE'\n" + REPAIR_SOURCE + "\nCTD_MOCK_SOURCE"}
    else:
        raise ValueError("agent did not advertise a supported file-editing tool")

    return {
        "tool_calls": [{
            "index": 0,
            "id": CALL_ID,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, separators=(",", ":"))},
        }]
    }, "tool_calls"


def native_scripted_reply(request: dict, *, reasoning: bool = False) -> bytes:
    """Script the same independent-verifier repair over native Responses SSE."""
    from native_responses_mock import events, REASONING_ID, OPAQUE_REASONING

    items = request.get("input")
    if not isinstance(items, list) or not items or request.get("stream") is not True:
        raise ValueError("native rehearsal expects streamed item history")
    if request.get("store") is not False or "prompt_cache_key" in request:
        raise ValueError("native metering normalization missing")
    if reasoning and (request.get("reasoning", {}).get("effort") != "low" or
                      request.get("include") != ["reasoning.encrypted_content"]):
        raise ValueError("missing native low-effort encrypted reasoning settings")
    outputs = [i for i in items if isinstance(i, dict) and i.get("type") == "function_call_output"]
    if outputs:
        if len(outputs) != 1 or outputs[0].get("call_id") != CALL_ID:
            raise ValueError("missing matched native tool result")
        if reasoning:
            reasoning_items = [i for i in items if isinstance(i, dict) and i.get("type") == "reasoning"]
            if (len(reasoning_items) != 1 or reasoning_items[0].get("id") != REASONING_ID
                    or reasoning_items[0].get("encrypted_content") != OPAQUE_REASONING):
                raise ValueError("opaque reasoning item missing or changed")
        item = {"type": "message", "id": "msg_ctd_repair", "role": "assistant",
                "status": "completed", "content": [
                    {"type": "output_text", "text": "The requested source change has been applied.",
                     "annotations": [], "logprobs": []}]}
        return events("resp_ctd_repair_2", item, tool=False, input_tokens=200, output_tokens=40)
    declared = {t.get("name") for t in request.get("tools", [])
                if isinstance(t, dict) and t.get("type") == "function"}
    if "write" not in declared:
        raise ValueError("native rehearsal needs Pi write tool")
    item = {"type": "function_call", "id": "fc_ctd_repair", "call_id": CALL_ID,
            "name": "write", "arguments": json.dumps({"path": "/app/allocate.py", "content": REPAIR_SOURCE}),
            "status": "completed"}
    return events("resp_ctd_repair_1", item, tool=True, input_tokens=100, output_tokens=400,
                  reasoning=reasoning)
