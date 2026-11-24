"""Read-only OpenAI model-access preflight. No inference or token spending."""
from __future__ import annotations
import http.client
import json
import os
import re
import ssl
from pathlib import Path
from typing import Any, Callable
from .core import ReceiptError
from .live_gateway import read_key

_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,120}\Z")
_MAX_BYTES = 8192

def _retrieve(model: str, credential: str) -> tuple[int, bytes]:
    """Request fixed-origin model metadata; never follow authorization redirects."""
    connection = http.client.HTTPSConnection("api.openai.com", timeout=15, context=ssl.create_default_context())
    try:
        connection.request("GET", f"/v1/models/{model}", headers={
            "Authorization": f"Bearer {credential}", "Accept": "application/json",
            "User-Agent": "cost-to-done-access-preflight/0.1",
        })
        response = connection.getresponse()
        return response.status, response.read(_MAX_BYTES + 1)
    finally:
        connection.close()

def probe_models(key_file: Path, models: tuple[str, ...],
                 *, transport: Callable[[str, str], tuple[int, bytes]] = _retrieve) -> dict[str, Any]:
    """Return only sanitized per-model access statuses, never API responses."""
    if not 1 <= len(models) <= 8 or len(set(models)) != len(models) or any(
        not isinstance(m, str) or not _MODEL.fullmatch(m) for m in models
    ):
        raise ReceiptError("provide one to eight distinct valid model IDs")
    path = Path(key_file)
    if path.is_symlink() or not path.is_file():
        raise ReceiptError("provider key must be an existing private regular file")
    if os.name == "posix" and path.stat().st_mode & 0o077:
        raise ReceiptError("provider key must be private (chmod 600)")
    key = read_key(path)
    findings = []
    for model in models:
        try:
            status, response = transport(model, key)
            if status == 200 and len(response) <= _MAX_BYTES:
                try:
                    body = json.loads(response.decode("utf-8"))
                    access = "metadata_available" if isinstance(body, dict) and (
                        body.get("object") == "model" and body.get("id") == model
                    ) else "unexpected_metadata"
                except (ValueError, UnicodeError):
                    access = "unexpected_metadata"
            else:
                access = {
                    401: "unauthorized", 403: "forbidden", 404: "model_not_available",
                    429: "rate_limited", 301: "redirect_refused", 302: "redirect_refused",
                    303: "redirect_refused", 307: "redirect_refused", 308: "redirect_refused",
                }.get(status, "provider_or_protocol_error")
        except (OSError, TimeoutError, ValueError, http.client.HTTPException):
            access = "transport_error"
        findings.append({"model": model, "access": access})
    return {
        "schema_version": 1, "check": "openai_model_metadata_only",
        "models": findings,
        "metadata_access_confirmed": any(x["access"] == "metadata_available" for x in findings),
        "inference_requests": 0, "provider_invoice_reconciled": False,
        "provider_spend_limit_verified": False,
    }
