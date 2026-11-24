"""One privileged, budget-admitted OpenAI Chat Completions protocol diagnostic.

Only the trusted gateway container path is used for normal experiments. This
short diagnostic uses the same fixed-origin transport and gateway admission
logic, with an intercepted upstream response summarized to safe metadata.
No raw model output, upstream error text, prompts or credentials are published.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import Any

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import (
    Gateway, PriceSchedule, UpstreamResponse, _stream_token_usage,
    openai_transport,
)
from cost_to_done.ledger import BudgetLedger
from cost_to_done.private_files import publish_private_texts

_SAFE = re.compile(r"[A-Za-z0-9_.:-]{1,120}\Z")


def classify_response(response: UpstreamResponse, requested_model: str) -> dict[str, Any]:
    """Classify only protocol metadata, excluding all provider message text."""
    output: dict[str, Any] = {
        "upstream_http_status": response.status,
        "mime": response.content_type.split(";", 1)[0].strip().lower(),
    }
    if response.status != 200:
        try:
            data = json.loads(response.body)
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                for name in ("type", "code", "param"):
                    val = err.get(name)
                    if isinstance(val, str) and _SAFE.fullmatch(val):
                        output["provider_error_" + name] = val
        except (ValueError, UnicodeError):
            pass
        return output

    if output["mime"] != "text/event-stream":
        output["gateway_protocol_result"] = "unexpected_mime"
        return output

    for line in response.body.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        try:
            data = json.loads(line[6:])
        except ValueError:
            continue
        if isinstance(data, dict):
            reported = data.get("model")
            if isinstance(reported, str) and _SAFE.fullmatch(reported):
                output["upstream_reported_model"] = reported
                break
    try:
        prompt, completion = _stream_token_usage(response.body, requested_model)
        output["gateway_protocol_result"] = "usage_and_terminal_framing_valid"
        output["prompt_tokens"] = prompt
        output["completion_tokens"] = completion
    except ReceiptError as exc:
        # The error originates in Cost to Done's fixed parser, not the model
        # response body. Publish only a narrow parser failure category.
        error = str(exc)
        categories = (
            "stream event model mismatch", "unsupported SSE event field",
            "stream is missing completion or usage events",
            "usage must appear once in the final data event",
            "stream lacks finish reason or complete terminal usage",
            "invalid terminal stream usage", "truncated terminal stream framing",
            "stream lacks an unambiguous final [DONE] marker",
        )
        output["gateway_protocol_result"] = next(
            (x.replace(" ", "_") for x in categories if x in error),
            "other_rejected_stream",
        )
    return output


def run(model: str, price_file: Path, key: str, directory: Path) -> dict[str, Any]:
    """Use a dedicated budget ledger and a minimal bounded tool-call prompt."""
    schedule = PriceSchedule.load(price_file)
    if model != schedule.model:
        raise ReceiptError("diagnostic price/model mismatch")
    ledger = BudgetLedger(directory / "ledger.sqlite3", budget_usd="0.25")
    observed: dict[str, Any] = {}
    def transport(body: bytes, credential: str) -> UpstreamResponse:
        response = openai_transport(body, credential)
        observed.update(classify_response(response, model))
        return response

    gateway = Gateway(
        ledger, schedule, client_token=secrets.token_urlsafe(32),
        provider_key=key, transport=transport,
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "Call the bash function to print OK."},
        ],
        "tools": [{
            "type": "function",
            "function": {
                "name": "bash", "description": "Execute a command",
                "parameters": {"type": "object", "properties": {
                    "command": {"type": "string"}
                }, "required": ["command"]},
            },
        }],
        "tool_choice": "auto",
        "stream": True,
        "stream_options": {"include_usage": True},
        "store": False,
        "max_completion_tokens": 256,
    }
    try:
        status, _ = gateway.handle(json.dumps(payload).encode(), "diagnostic-1")
        observed["gateway_http_status"] = status
    except Exception:
        observed["gateway_http_status"] = "rejected_or_transport_error"
    snapshot = ledger.snapshot()
    observed.update({
        "model": model, "ledger_settled_rate_card_estimate_usd": snapshot.settled,
        "ledger_uncertain": snapshot.uncertain,
        "inference_requests": 1 if ledger.entries() else 0,
        "provider_invoice_reconciled": False,
        "provider_hard_spend_limit_verified": False,
        "purpose": "private_credential_protocol_diagnostic_not_model_evaluation",
    })
    return observed


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--prices", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    key = os.environ.pop("CTD_OPENAI_SECRET", "")
    if not key:
        print('{"status":"repository_secret_unavailable","inference_requests":0}')
        return 2
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as private:
        result = run(args.model, args.prices, key, Path(private))
        del key
    publish_private_texts([(args.output, json.dumps(result, sort_keys=True, indent=2) + "\n")])
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("upstream_http_status") == 200 else 2


if __name__ == "__main__":
    raise SystemExit(main())
