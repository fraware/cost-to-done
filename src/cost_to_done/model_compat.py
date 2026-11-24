"""Explicit OpenAI API tool-calling compatibility policy for the v0.1 harness.

The installed Pi agent and the metering gateway currently use Chat
Completions. Some later OpenAI models expose that endpoint for text, but
require the Responses API for tool calls. The list is intentionally narrow,
date-scoped and fail-closed for the models verified against the official
deployment checklist on 2026-11-23. This is not a general model registry.
"""
from __future__ import annotations

import re

from .core import ReceiptError

_RESPONSES_FOR_TOOLS = re.compile(
    r"(?:gpt-6\.2-(?:sol|astra)|gpt-6\.1-(?:terra|sol)|gpt-6-astra)(?:-|$)"
)
_CHAT_NONE_TOOLS = re.compile(r"gpt-5\.4(?:-mini)?(?:-|$)")


def needs_responses_for_tools(model: str) -> bool:
    """Whether this known OpenAI model requires Responses for function tools."""
    return isinstance(model, str) and _RESPONSES_FOR_TOOLS.match(model) is not None


def chat_tools_need_no_reasoning(model: str) -> bool:
    """Whether Chat Completions function tools must use reasoning_effort=none."""
    return isinstance(model, str) and _CHAT_NONE_TOOLS.match(model) is not None


def validate_chat_tool_route(model: str) -> None:
    """Reject known Responses-only tool models before issuing a provider call."""
    if needs_responses_for_tools(model):
        raise ReceiptError(
            f"{model}: tool calling requires the OpenAI Responses API; "
            "this runner only supports Chat Completions"
        )
