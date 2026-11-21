"""Inspect matched Harbor jobs side by side without asserting a model ranking.

Harbor's trial files are observations supplied by the operator. They are neither
independent verifier attestations nor provider invoices. This module only
compares records with matching task identifiers and Harbor task checksums.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
from typing import Any, Sequence

from .core import ReceiptError

_MAX_CONFIGS = 8
_MAX_TASKS = 2000
_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?\Z")


def _inspect_harbor_job(job: Path) -> dict[str, Any]:
    """Defer import to keep the comparison independent of execution tooling."""
    from .harbor import inspect_harbor_job

    return inspect_harbor_job(job)


def _parse_spec(value: str) -> tuple[str, Path]:
    """Parse a strictly named local job specification, NAME=PATH."""
    if not isinstance(value, str) or "=" not in value:
        raise ReceiptError("each job must be NAME=PATH (e.g. fast=./runs/fast)")
    label, raw_path = value.split("=", 1)
    if not _LABEL_RE.fullmatch(label) or not raw_path:
        raise ReceiptError("job label must be 1–64 ASCII letters, digits, dots, dashes or underscores")
    return label, Path(raw_path)


def _cost(value: Any) -> Decimal | None:
    """Read exact Harbor-reported USD; missing values are never zero-filled."""
    if value is None:
        return None
    if not isinstance(value, str) or not _AMOUNT.fullmatch(value):
        raise ReceiptError("Harbor cost estimate must be an exact decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ReceiptError("invalid Harbor monetary estimate") from exc
    if not result.is_finite() or result < 0:
        raise ReceiptError("negative or nonfinite cost estimate")
    return result


def _checked_trial(trial: Any, label: str) -> dict[str, Any]:
    if not isinstance(trial, dict):
        raise ReceiptError(f"{label}: malformed Harbor trial")
    task = trial.get("task")
    checksum = trial.get("task_checksum")
    digest = trial.get("raw_result_sha256")
    outcome = trial.get("outcome")
    seconds = trial.get("elapsed_seconds")
    if not isinstance(task, str) or not task.strip() or len(task) > 256:
        raise ReceiptError(f"{label}: invalid Harbor task name")
    if not isinstance(checksum, str) or not _SHA256.fullmatch(checksum):
        raise ReceiptError(f"{label}: missing or invalid task checksum")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ReceiptError(f"{label}: missing or invalid result-file hash")
    if outcome not in ("pass", "fail", "infrastructure_error"):
        raise ReceiptError(f"{label}: unsupported outcome")
    if type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0:
        raise ReceiptError(f"{label}: invalid elapsed time")
    agent = trial.get("agent")
    model = trial.get("model")
    if not isinstance(agent, str) or not agent or len(agent) > 128:
        raise ReceiptError(f"{label}: invalid agent identifier")
    if model is not None and (not isinstance(model, str) or not model or len(model) > 128):
        raise ReceiptError(f"{label}: invalid model identifier")
    price = _cost(trial.get("agent_reported_cost_usd"))
    if (price is None) != (trial.get("cost_status") == "unavailable"):
        raise ReceiptError(f"{label}: inconsistent cost-availability status")
    if price is not None and trial.get("cost_status") != "agent_reported_estimate":
        raise ReceiptError(f"{label}: unsupported cost provenance")
    return {
        "task": task,
        "task_checksum": checksum,
        "raw_result_sha256": digest,
        "outcome": outcome,
        "elapsed_seconds": seconds,
        "agent": agent,
        "model": model,
        "cost_usd": format(price, "f") if price is not None else None,
    }


def compare_harbor_jobs(specs: Sequence[str]) -> dict[str, Any]:
    """Compare 2–8 complete, singly replicated jobs with identical task inputs.

    A paired task matrix is useful for triage; its numbers are not proof of
    model quality, independent verifier success, or actual billed USD.
    """
    if not 2 <= len(specs) <= _MAX_CONFIGS:
        raise ReceiptError(f"compare-harbor accepts 2–{_MAX_CONFIGS} named jobs")
    configurations: list[dict[str, Any]] = []
    names: set[str] = set()
    job_paths: list[Path] = []
    rows_by_job: list[dict[str, dict[str, Any]]] = []
    reference: dict[str, str] | None = None
    for spec in specs:
        name, raw_path = _parse_spec(spec)
        if name in names:
            raise ReceiptError(f"duplicate job name: {name}")
        names.add(name)
        if raw_path.is_symlink() or not raw_path.is_dir():
            raise ReceiptError(f"{name}: job must be a real directory")
        path = raw_path.resolve(strict=True)
        if path in job_paths:
            raise ReceiptError("multiple labels refer to the same Harbor job")
        job_paths.append(path)
        inspected = _inspect_harbor_job(path)
        if inspected.get("complete") is not True:
            raise ReceiptError(f"{name}: job is incomplete or lacks its trial-count manifest")
        source = inspected.get("trials")
        if (not isinstance(source, list) or not source or len(source) > _MAX_TASKS
                or inspected.get("observed_trials") != len(source)):
            raise ReceiptError(f"{name}: invalid or unsupported trial count")
        keyed: dict[str, dict[str, Any]] = {}
        for raw_trial in source:
            item = _checked_trial(raw_trial, name)
            key = item["task"]
            if key in keyed:
                raise ReceiptError(f"{name}: repeated task {key!r}; v1 needs one trial per task")
            keyed[key] = item
        fingerprint = {task: item["task_checksum"] for task, item in keyed.items()}
        if reference is None:
            reference = fingerprint
        elif fingerprint != reference:
            different = sorted(set(fingerprint).symmetric_difference(reference))
            changed = sorted(k for k in set(fingerprint).intersection(reference)
                             if fingerprint[k] != reference[k])
            raise ReceiptError(f"{name}: task/checksum mismatch (missing or extra={different[:4]}, changed={changed[:4]})")
        rows_by_job.append(keyed)
        amounts = [_cost(item["cost_usd"]) for item in keyed.values()]
        all_priced = all(value is not None for value in amounts)
        total = sum((value for value in amounts if value is not None), Decimal(0))
        configurations.append({
            "name": name,
            "job": path.name,
            "trials": len(keyed),
            "passed": sum(item["outcome"] == "pass" for item in keyed.values()),
            "failed": sum(item["outcome"] == "fail" for item in keyed.values()),
            "infrastructure_errors": sum(item["outcome"] == "infrastructure_error" for item in keyed.values()),
            "missing_costs": sum(value is None for value in amounts),
            "total_agent_reported_estimate_usd": format(total, "f") if all_priced else None,
            "total_seconds": sum(item["elapsed_seconds"] for item in keyed.values()),
        })
    assert reference is not None
    tasks = []
    for task in sorted(reference):
        tasks.append({
            "task": task,
            "task_checksum": reference[task],
            "observations": [
                {"configuration": cfg["name"], **job[task]}
                for cfg, job in zip(configurations, rows_by_job)
            ],
        })
    return {
        "schema_version": 1,
        "source": "Harbor trial files supplied by the operator",
        "paired_tasks_verified_by_declared_checksum": True,
        "independent_verifier_audit": False,
        "provider_invoice_reconciled": False,
        "eligible_for_ranking": False,
        "cost_basis": "agent_reported_estimate_when_available",
        "warnings": [
            "Recorded verifier results have not been independently re-executed.",
            "Agent-reported costs are not provider invoices; missing amounts invalidate complete spend totals.",
            "Results are descriptive: no randomization, replication, uncertainty estimate or model ranking is inferred.",
        ],
        "configurations": configurations,
        "tasks": tasks,
        "job_paths": job_paths,
    }


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


def _amount(value: str | None) -> str:
    return _text("Unavailable" if value is None else "$" + value)


def render_harbor_comparison(summary: dict[str, Any], *, title: str = "Harbor comparison") -> str:
    """Render a fully standalone HTML document with no third-party assets."""
    if not isinstance(title, str) or not 1 <= len(title) <= 140:
        raise ReceiptError("report title must contain 1–140 characters")
    heads = "".join(f"<th scope='col'>{_text(c['name'])}</th>" for c in summary["configurations"])
    body = []
    for task in summary["tasks"]:
        cells = []
        for observation in task["observations"]:
            status = observation["outcome"]
            cost = _amount(observation["cost_usd"])
            cells.append(
                f"<td><strong class='result'>{_text(status.upper())}</strong>"
                f"<span class='minor'>{cost} agent estimate</span>"
                f"<span class='minor'>{_text(format(observation['elapsed_seconds'], '.2f'))} s · "
                f"{_text(observation['agent'])} · {_text(observation['model'] or 'no model')}</span>"
                f"<code title='Raw trial JSON SHA-256'>{_text(observation['raw_result_sha256'][:16])}…</code></td>"
            )
        body.append(f"<tr><th scope='row'>{_text(task['task'])}<small title='Harbor task checksum'>"
                    f"{_text(task['task_checksum'][:16])}…</small></th>{''.join(cells)}</tr>")
    cards = []
    for config in summary["configurations"]:
        cards.append(f"<div class='card'><span>{_text(config['name'])}</span>"
                     f"<strong>{config['passed']} / {config['trials']}</strong>"
                     f"<small>Harbor-recorded passes</small>"
                     f"<p>{_amount(config['total_agent_reported_estimate_usd'])}"
                     f" <small>estimated total · {config['missing_costs']} missing</small></p></div>")
    notes = "".join(f"<li>{_text(note)}</li>" for note in summary["warnings"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>{_text(title)} — Cost to Done</title>
<style>
:root{{--paper:#f8f7f3;--ink:#171918;--muted:#565e5a;--line:#c4c7c0;--blue:#1c4e62}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif}}
main{{max-width:1360px;margin:auto;padding:42px clamp(20px,4vw,64px) 72px}}
header{{border-bottom:2px solid var(--ink);padding-bottom:20px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}}
.brand,.tag,th,code,small{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}.brand{{font-size:14px;font-weight:750;letter-spacing:.01em}}
.tag{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--blue)}}h1{{font:normal clamp(38px,5vw,68px)/1.1 Georgia,serif;letter-spacing:-.05em;margin:58px 0 18px}}
.lead{{max-width:790px;color:var(--muted);margin:0 0 36px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.card{{padding:22px 18px 15px 0}}.card+.card{{border-left:1px solid var(--line);padding-left:18px}}.card>span{{display:block;font-weight:700;font-size:13px}}.card strong{{display:block;font:normal 43px Georgia,serif;margin:12px 0 0}}.card small{{color:var(--muted);font-size:11px}}.card p{{margin:14px 0 0;font-family:ui-monospace,monospace;font-size:15px}}
section{{margin-top:60px}}h2{{font:normal 31px Georgia,serif;margin:0 0 16px}}.scroll{{overflow:auto;border-top:2px solid var(--ink)}}table{{border-collapse:collapse;width:100%;min-width:780px}}th,td{{text-align:left;padding:17px;border-bottom:1px solid var(--line);vertical-align:top}}thead th{{font-size:11px;text-transform:uppercase;letter-spacing:.04em}}tbody th{{font-size:13px;max-width:320px;overflow-wrap:anywhere}}tbody th small{{display:block;color:var(--muted);font-size:11px;font-weight:400;margin-top:8px}}.result{{display:block;font-size:12px}}
.minor,td code{{display:block;font-size:11px;color:var(--muted);margin-top:6px;overflow-wrap:anywhere}}ul{{padding-left:22px;max-width:910px}}li{{margin:8px 0}}footer{{margin-top:70px;border-top:1px solid var(--line);padding-top:16px;color:var(--muted);font-size:11px}}
@media(max-width:650px){{.card+.card{{border-left:0;padding-left:0}}.cards{{grid-template-columns:1fr 1fr}}main{{padding-top:20px}}}}
</style></head><body><main><header><div class="brand">COST TO DONE / HARBOR</div><div class="tag">DESCRIPTIVE OBSERVATIONS · NO RANKING</div></header>
<h1>{_text(title)}</h1><p class="lead">Identical Harbor task identifiers and task checksums are checked before comparison. Outcomes and cost estimates are as recorded by Harbor. This report is not independent verification or a provider-billing statement.</p>
<div class="cards">{''.join(cards)}</div>
<section><h2>Same work, side by side</h2><div class="scroll"><table><thead><tr><th scope='col'>Task</th>{heads}</tr></thead><tbody>{''.join(body)}</tbody></table></div></section>
<section><h2>Limits of interpretation</h2><ul>{notes}</ul></section><footer>Generated locally · No external fonts, scripts, analytics or network calls · Raw trial files retained unchanged</footer>
</main></body></html>"""


def write_harbor_comparison(specs: Sequence[str], output: Path, *, title: str = "Harbor comparison") -> dict[str, Any]:
    """Write a private, immutable-output HTML report; never modify source jobs."""
    summary = compare_harbor_jobs(specs)
    path = Path(output)
    if path.exists() or path.is_symlink() or not path.name:
        raise ReceiptError("output already exists or is invalid; refusing overwrite")
    resolved_output = path.resolve(strict=False)
    if any(resolved_output.is_relative_to(job) for job in summary["job_paths"]):
        raise ReceiptError("output must remain outside original Harbor job directories")
    html = render_harbor_comparison(summary, title=title)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(html)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    data = html.encode("utf-8")
    return {
        "output": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "task_count": len(summary["tasks"]),
        "configuration_count": len(summary["configurations"]),
        "eligible_for_ranking": False,
        "independent_verifier_audit": False,
        "provider_invoice_reconciled": False,
        "cost_basis": "agent_reported_estimate_when_available",
    }
