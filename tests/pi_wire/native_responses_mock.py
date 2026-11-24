"""Exercise the pinned Pi native Responses client against a scripted local provider.

No provider credentials or live model calls. The provider writes request shapes
only, and asks Pi to create a sentinel file in a disposable task directory.
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL = "test-model-1"
TOKEN = "ctd-native-wire-probe-token-00001"
SENTINEL = "native-responses-wire-ok\n"


def shape(value):
    """Keep structural information, never prompt text, arguments or secrets."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v) for v in value]
    return type(value).__name__


def events(response_id, item, *, tool):
    model = {"id": response_id, "object": "response", "created_at": 0,
             "model": MODEL, "status": "in_progress", "output": [], "usage": None}
    initial = dict(item)
    initial["status"] = "in_progress"
    if tool:
        initial["arguments"] = ""
    else:
        initial["content"] = []
    values = [
        {"type": "response.created", "response": model},
        {"type": "response.in_progress", "response": model},
        {"type": "response.output_item.added", "output_index": 0, "item": initial},
    ]
    if tool:
        values += [
            {"type": "response.function_call_arguments.delta", "output_index": 0,
             "item_id": item["id"], "delta": item["arguments"]},
            {"type": "response.function_call_arguments.done", "output_index": 0,
             "item_id": item["id"], "arguments": item["arguments"], "name": item["name"]},
        ]
    else:
        part = item["content"][0]
        values += [
            {"type": "response.content_part.added", "output_index": 0, "content_index": 0,
             "item_id": item["id"], "part": {"type": "output_text", "text": "", "annotations": []}},
            {"type": "response.output_text.delta", "output_index": 0, "content_index": 0,
             "item_id": item["id"], "delta": part["text"], "logprobs": []},
            {"type": "response.output_text.done", "output_index": 0, "content_index": 0,
             "item_id": item["id"], "text": part["text"], "logprobs": []},
            {"type": "response.content_part.done", "output_index": 0, "content_index": 0,
             "item_id": item["id"], "part": part},
        ]
    values += [
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        {"type": "response.completed", "response": {
            **model, "status": "completed", "output": [item],
            "usage": {"input_tokens": 100, "output_tokens": 40, "total_tokens": 140,
                      "input_tokens_details": {"cached_tokens": 0},
                      "output_tokens_details": {"reasoning_tokens": 0}}}},
    ]
    return b"".join(b"event: " + v["type"].encode() + b"\ndata: " +
                    json.dumps({**v, "sequence_number": i}).encode() + b"\n\n"
                    for i, v in enumerate(values))


class Handler(BaseHTTPRequestHandler):
    requests = []
    lock = threading.Lock()
    evidence: Path
    target: Path

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/ready" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        if self.headers.get("Authorization") != "Bearer " + TOKEN:
            self.send_error(403)
            return
        try:
            length = int(self.headers["Content-Length"])
            if not 0 < length <= 256_000:
                raise ValueError("request size")
            body = json.loads(self.rfile.read(length))
            if body.get("model") != MODEL or body.get("stream") is not True:
                raise ValueError("unexpected route")
            with self.lock:
                number = len(self.requests)
                self.requests.append({
                    "keys": sorted(body),
                    "shape": shape(body),
                    "input_types": [v.get("type", "message") for v in body.get("input", [])
                                    if isinstance(v, dict)],
                    "store": body.get("store"),
                    "max_output_tokens": body.get("max_output_tokens"),
                })
                self.evidence.write_text(json.dumps(self.requests, indent=2), encoding="utf-8")
                if number == 0:
                    if not any(t.get("type") == "function" and t.get("name") == "write"
                               for t in body.get("tools", [])):
                        raise ValueError("Pi write tool missing")
                    item = {"type": "function_call", "id": "fc_ctd_probe", "call_id": "call_ctd_probe",
                            "name": "write", "arguments": json.dumps({
                                "path": str(self.target), "content": SENTINEL}),
                            "status": "completed"}
                    payload = events("resp_ctd_1", item, tool=True)
                elif number == 1:
                    if not any(v.get("type") == "function_call_output"
                               and v.get("call_id") == "call_ctd_probe"
                               for v in body.get("input", []) if isinstance(v, dict)):
                        raise ValueError("missing matched function output")
                    if self.target.read_text(encoding="utf-8") != SENTINEL:
                        raise ValueError("actual local tool effect missing")
                    item = {"type": "message", "id": "msg_ctd_probe", "role": "assistant",
                            "status": "completed", "content": [
                                {"type": "output_text", "text": "OK", "annotations": [], "logprobs": []}]}
                    payload = events("resp_ctd_2", item, tool=False)
                else:
                    raise ValueError("unexpected extra request")
        except (ValueError, TypeError, KeyError, OSError, AttributeError):
            self.send_error(400, "native wire probe failed")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    Handler.evidence = args.evidence.resolve()
    Handler.target = args.target.resolve()
    ThreadingHTTPServer(("127.0.0.1", 8879), Handler).serve_forever()
