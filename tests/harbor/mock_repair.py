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
