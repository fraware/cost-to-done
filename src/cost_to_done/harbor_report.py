"""Render an offline, unranked Harbor evidence overview from recorded trial files.

The report deliberately does not authenticate Harbor's verifier, replicate an
inference invoice, or compare models. It accepts only the conservative output
of ``inspect_harbor_job`` and uses no JavaScript, CDN, or external fonts.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path
import os
import re
from typing import Any

from .core import ReceiptError
from .harbor import inspect_harbor_job

_MAX_TRIALS = 2_000
_MAX_TITLE_LENGTH = 140
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_USD_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?\Z")
_CSS = """
:root { color-scheme: light; --ink:#1c1c1a; --paper:#f9f9f6; --muted:#66665e; --rule:#d5d5cd; --good:#185b42; --bad:#9e4235; }
*{box-sizing:border-box}html{background:var(--paper)}body{margin:0;font-family:Arial,Helvetica,sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
.page{width:min(1160px,calc(100% - 52px));margin:auto}header{border-bottom:2px solid var(--ink);padding:24px 0;display:flex;justify-content:space-between;gap:20px;align-items:baseline}
.brand{font:bold 13px ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:-.04em}.sup{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;text-transform:uppercase;color:var(--muted)}
.hero{padding:78px 0 48px;border-bottom:1px solid var(--rule)}.kicker{font:700 11px ui-monospace,Consolas,monospace;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
h1{font:500 clamp(42px,6vw,82px)/1.03 Arial,Helvetica,sans-serif;letter-spacing:-.075em;max-width:850px;margin:17px 0 24px;overflow-wrap:anywhere}
.lede{max-width:820px;font:16px/1.55 Arial,sans-serif;color:#50504c;margin:0}.label{display:inline-block;border:1px solid var(--ink);font:700 11px ui-monospace,Consolas,monospace;padding:7px 9px;letter-spacing:.03em;margin-top:27px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:2px solid var(--ink)}.metric{padding:26px 20px 26px 0;min-width:0}.metric+.metric{border-left:1px solid var(--rule);padding-left:22px}
.metric .head{display:block;font:11px ui-monospace,Consolas,monospace;text-transform:uppercase;color:var(--muted)}.metric strong{display:block;margin:17px 0 6px;font:500 clamp(24px,3vw,40px) Arial,sans-serif;letter-spacing:-.065em}
.metric small{font:11px/1.5 ui-monospace,Consolas,monospace;color:var(--muted)}section{margin:56px 0}h2{font:500 27px Arial,Helvetica,sans-serif;letter-spacing:-.04em;margin:0 0 16px}
.sectionhead{display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap}.hint{font:11px/1.5 ui-monospace,Consolas,monospace;color:var(--muted)}
.tablewrap{overflow:auto;border-top:2px solid var(--ink)}table{border-collapse:collapse;width:100%;min-width:760px}th{text-align:left;font:700 10px ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:16px 12px;border-bottom:1px solid var(--rule)}
td{border-bottom:1px solid var(--rule);font:13px/1.4 Arial,sans-serif;padding:15px 12px;vertical-align:top;overflow-wrap:anywhere}td.mono{font:12px/1.5 ui-monospace,Consolas,monospace;white-space:nowrap}
.meta{display:block;color:var(--muted);font:11px/1.5 ui-monospace,Consolas,monospace;margin-top:5px}.status{font:700 11px ui-monospace,Consolas,monospace;letter-spacing:.01em}.pass{color:var(--good)}.fail{color:var(--bad)}.error{color:var(--bad)}
.notice{padding:22px 0;border-top:2px solid var(--ink);display:grid;grid-template-columns:200px 1fr;gap:22px}.notice strong{font:700 11px ui-monospace,Consolas,monospace;text-transform:uppercase;letter-spacing:.03em}.notice p{font:14px/1.6 Arial,sans-serif;color:#52524e;margin:0;max-width:810px}
footer{padding:34px 0 60px;border-top:1px solid var(--rule);font:11px/1.5 ui-monospace,Consolas,monospace;color:var(--muted);display:flex;justify-content:space-between;gap:24px}
@media(max-width:780px){.page{width:min(100% - 34px,1160px)}.hero{padding:54px 0 36px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.metric:nth-child(3){border-left:0;padding-left:0;border-top:1px solid var(--rule)}.metric:nth-child(4){border-top:1px solid var(--rule)}.notice{grid-template-columns:1fr;gap:8px}}
@media(max-width:470px){.metrics{grid-template-columns:1fr}.metric+.metric{border-left:0;border-top:1px solid var(--rule);padding-left:0}footer{display:block}}
"""


def _text(value: Any) -> str:
    """Escape untrusted Harbor labels before inserting them into HTML."""
    return escape(str(value), quote=True)


def _estimated_cost(value: Any) -> Decimal | None:
    """Interpret a recorded positive or zero agent estimate, never a bill."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReceiptError("Harbor cost must be a decimal string or absent")
    if _USD_DECIMAL.fullmatch(value) is None:
        raise ReceiptError("invalid Harbor cost estimate: expected a plain decimal with up to 12 places")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ReceiptError("invalid Harbor cost estimate") from exc
    if not amount.is_finite() or amount < 0 or amount > 100_000_000:
        raise ReceiptError("invalid Harbor cost estimate")
    return amount


def _usd(value: Decimal | None) -> str:
    """Display micro-dollar estimates without mislabeling missing data as zero."""
    if value is None:
        return "Unavailable"
    printed = format(value, "f")
    if "." in printed:
        printed = printed.rstrip("0").rstrip(".")
    return "$" + printed


def _safe_rows(job: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(job, dict):
        raise ReceiptError("Harbor inspection must be an object")
    rows = job.get("trials")
    if not isinstance(rows, list) or not 1 <= len(rows) <= _MAX_TRIALS:
        raise ReceiptError(f"report supports 1 to {_MAX_TRIALS} recorded trials")
    if job.get("observed_trials") != len(rows):
        raise ReceiptError("Harbor inspection trial count mismatch")
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ReceiptError("trial row must be an object")
        trial_id = row.get("id")
        if not isinstance(trial_id, str) or not trial_id or len(trial_id) > 256 or trial_id in seen:
            raise ReceiptError("invalid or repeated Harbor trial ID")
        seen.add(trial_id)
        for key in ("task", "agent", "task_checksum", "raw_result_sha256"):
            if not isinstance(row.get(key), str) or not row[key] or len(row[key]) > 500:
                raise ReceiptError(f"invalid {key} field")
        for digest_name in ("task_checksum", "raw_result_sha256"):
            if _SHA256.fullmatch(row[digest_name]) is None:
                raise ReceiptError(f"invalid {digest_name} SHA-256 digest")
        if row.get("outcome") not in {"pass", "fail", "infrastructure_error"}:
            raise ReceiptError("unrecognized Harbor outcome")
        elapsed = row.get("elapsed_seconds")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (float, int)) or not (0 <= elapsed < 10**9):
            raise ReceiptError("invalid Harbor elapsed time")
        from math import isfinite
        if not isfinite(elapsed):
            raise ReceiptError("nonfinite Harbor elapsed time")
        if row.get("cost_status") not in {"agent_reported_estimate", "unavailable"}:
            raise ReceiptError("unsupported Harbor cost source")
        cost = _estimated_cost(row.get("agent_reported_cost_usd"))
        if (cost is None) != (row["cost_status"] == "unavailable"):
            raise ReceiptError("cost source conflicts with amount")
        clean.append({**row, "_cost": cost})
    return clean


def render_harbor_overview(job: dict[str, Any], *, title: str = "Harbor run") -> str:
    """Generate an offline evidence dashboard with deliberately unranked records.

    Financial totals remain unreported when any trial lacks an estimated cost.
    This prevents presenting a partial sum as the cost of the job.
    """
    if not isinstance(title, str) or not title.strip() or len(title) > _MAX_TITLE_LENGTH:
        raise ReceiptError("report title must be nonempty and no longer than 140 characters")
    rows = _safe_rows(job)
    pass_count = sum(row["outcome"] == "pass" for row in rows)
    fail_count = sum(row["outcome"] == "fail" for row in rows)
    error_count = len(rows) - pass_count - fail_count
    have_all_costs = all(row["_cost"] is not None for row in rows)
    fully_enumerated = job.get("complete") is True
    total = sum((row["_cost"] for row in rows), Decimal(0)) if have_all_costs else None
    # Even a complete job has only agent estimates unless provider invoices are checked.
    prices_label = "Recorded costs available" if have_all_costs else "Cost evidence incomplete"
    run_status = "Trial roster complete" if fully_enumerated else "Trial roster unconfirmed"
    costs = "Agent-reported; observed trials only" if have_all_costs else "Missing cost estimates"
    body = []
    for row in rows:
        model = row.get("model") or "Model unspecified"
        provider = row.get("provider") or "Provider unspecified"
        outcome = row["outcome"]
        outcome_label = "INFRA ERROR" if outcome == "infrastructure_error" else outcome.upper()
        body.append(
            "<tr>"
            f"<td><strong>{_text(row['task'])}</strong><span class='meta'>SHA256 {_text(row['task_checksum'])}</span></td>"
            f"<td><strong>{_text(row['agent'])}</strong><span class='meta'>{_text(provider)} / {_text(model)}</span></td>"
            f"<td class='mono'><span class='status {outcome if outcome != 'infrastructure_error' else 'error'}'>{outcome_label}</span></td>"
            f"<td class='mono'>{row['elapsed_seconds']:.1f}s</td>"
            f"<td class='mono'>{_text(_usd(row['_cost']))}<span class='meta'>{'Agent estimate' if row['_cost'] is not None else 'No cost data'}</span></td>"
            f"<td class='mono'><span title='{_text(row['raw_result_sha256'])}'>{_text(row['raw_result_sha256'])[:16]}…</span><span class='meta'>trial {_text(row['id'])}</span></td>"
            "</tr>"
        )
    safe_title = _text(title)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{safe_title} | Cost to Done</title><style>{_CSS}</style></head><body>
<div class="page"><header><div class="brand">COST TO DONE / EVIDENCE</div><div class="sup">LOCAL / OFFLINE / NO TRACKERS</div></header>
<main><div class="hero"><div class="kicker">Harbor inspection · unranked evidence</div><h1>{safe_title}</h1>
<p class="lede">Task outcomes recorded by Harbor, execution time, and agent-reported cost estimates. Data is presented as observed by the local job inspector; verifier integrity, workload comparability, and provider billing require separate checks.</p>
<span class="label">{run_status.upper()} · {prices_label.upper()}</span></div>
<div class="metrics"><div class="metric"><span class="head">Observed trials</span><strong>{len(rows)}</strong><small>Harbor job records</small></div>
<div class="metric"><span class="head">Reported passes</span><strong>{pass_count}</strong><small>{fail_count} failed · {error_count} infrastructure errors</small></div>
<div class="metric"><span class="head">Observed estimated cost</span><strong>{_text(_usd(total))}</strong><small>{_text(costs)}</small></div>
<div class="metric"><span class="head">Comparison status</span><strong>Unranked</strong><small>Evidence only · no model ranking</small></div></div>
<section><div class="sectionhead"><h2>Execution records</h2><div class="hint">SHA-256 digests from raw trial result files</div></div><div class="tablewrap"><table><thead><tr><th>Task / checksum</th><th>Agent / route</th><th>Harbor result</th><th>Elapsed</th><th>Cost evidence</th><th>Raw receipt</th></tr></thead><tbody>{''.join(body)}</tbody></table></div></section>
<section class="notice"><strong>Interpretation boundary</strong><p>A Harbor-reported pass is not independently re-executed by this command. Costs shown here are agent-reported estimates, not invoices. Missing estimates invalidate the total. Distinct agents, task sets, and retry policies are not ranked. This report includes no task source code, prompt transcript, or provider credentials.</p></section>
<section class="notice"><strong>Reproduce and audit</strong><p>Review the referenced Harbor job locally. Each raw-result digest identifies the JSON artifact read by the inspector; it does not attest to its origin. This document is static and self-contained, with no JavaScript or external network dependencies.</p></section></main>
<footer><span>COST TO DONE / DIRECT HARBOR INSPECTION</span><span>Evidence summary v0.1 · No independent invoice verification</span></footer></div>
</body></html>"""


def write_harbor_overview(job_dir: Path, output: Path, *, title: str = "Harbor run") -> dict[str, Any]:
    """Inspect local Harbor results and exclusively create one offline HTML file.

    The destination must be outside the job tree and must not preexist. Harbor's
    original job evidence is never overwritten or modified by this command.
    """
    if output.is_symlink() or output.exists():
        raise ReceiptError("report output already exists; use a new path")
    job_root = job_dir.resolve(strict=True)
    destination = output.resolve(strict=False)
    if destination == job_root or destination.is_relative_to(job_root):
        raise ReceiptError("report output must be outside the Harbor job directory")
    if output.parent.is_symlink() or not output.parent.is_dir():
        raise ReceiptError("report output parent must be an existing real directory")
    inspected = inspect_harbor_job(job_dir)
    markup = render_harbor_overview(inspected, title=title)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(markup)
    return {"status": "written", "path": str(output), "observed_trials": inspected["observed_trials"],
            "roster_complete": inspected["complete"] is True,
            "cost_basis": "agent_reported_estimate_or_unavailable", "billing_verified": False,
            "ranking_generated": False}
