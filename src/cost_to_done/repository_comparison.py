"""Matched fictional repository comparison with explicit planned support.

This protocol is intentionally restricted to the two scripted CI scenarios.
It cannot be interpreted as model performance or real provider expenditure.
Missing or unsettled episodes withhold every cost-per-completion ratio.
"""
from __future__ import annotations

import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .ledger import _units, _usd
from .private_files import publish_private_texts
from .repository_task import _canonical

SCENARIOS = ("repository-addition-incorrect", "repository-addition-repair")
NETWORK_CHECKS = ["gateway_reachable", "direct_provider_dns_blocked",
                  "direct_provider_ip_blocked", "public_ip_blocked"]


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def build_comparison_plan(task_sha256: str, qualification_sha256: str,
                          price_schedule_sha256: str) -> dict:
    """Freeze both episodes before invoking any mock transport."""
    if not all(is_digest(x) for x in (task_sha256, qualification_sha256, price_schedule_sha256)):
        raise ReceiptError("invalid comparison input digest")
    plan = {"schema_version": 1, "scope": "fictional_repository_rehearsal",
            "task_input_sha256": task_sha256, "qualification_sha256": qualification_sha256,
            "price_schedule_sha256": price_schedule_sha256, "model": "test-model-1",
            "api": "responses", "reasoning_effort": "low", "allowance_per_episode_usd": "5",
            "paid_execution_authorized": False, "trials": list(SCENARIOS)}
    plan["plan_sha256"] = digest(plan)
    return plan


def summarize_comparison(plan: dict, observations: list[dict]) -> dict:
    """Retain all planned episodes, known costs, and missing observations."""
    if not isinstance(plan, dict) or plan != build_comparison_plan(
            plan.get("task_input_sha256"), plan.get("qualification_sha256"),
            plan.get("price_schedule_sha256")):
        raise ReceiptError("invalid frozen comparison plan")
    seen = {}
    result_hashes = set()
    task_checksums = set()
    for rec in observations:
        if not isinstance(rec, dict):
            raise ReceiptError("invalid comparison observation")
        scenario = rec.get("scenario")
        if (scenario not in SCENARIOS or scenario in seen
                or rec.get("plan_sha256") != plan["plan_sha256"]
                or rec.get("repository_task_sha256") != plan["task_input_sha256"]
                or rec.get("qualification_sha256") != plan["qualification_sha256"]
                or rec.get("price_schedule_sha256") != plan["price_schedule_sha256"]
                or rec.get("model") != plan["model"]
                or rec.get("api") != plan["api"] or rec.get("reasoning_effort") != plan["reasoning_effort"]
                or rec.get("mock_only") is not True or rec.get("billing_verified") is not False
                or rec.get("repository_execution_scope") != "mock_only"):
            raise ReceiptError("comparison observation identity or scope mismatch")
        state = rec.get("verifier_outcome")
        known = rec.get("fictional_rate_card_usd")
        if known is not None:
            _units(known)
        raw_hash = rec.get("harbor_trial_sha256")
        if raw_hash is not None:
            if not is_digest(raw_hash) or raw_hash in result_hashes:
                raise ReceiptError("invalid or repeated Harbor result identity")
            result_hashes.add(raw_hash)
        settled = (rec.get("status") == "isolated-live-runner-mock-verified"
                   and state in ("pass", "fail") and known is not None
                   and _units(known) <= _units(plan["allowance_per_episode_usd"])
                   and type(rec.get("gateway_calls")) is int and rec["gateway_calls"] > 0
                   and rec.get("network_checks") == NETWORK_CHECKS
                   and rec.get("opaque_reasoning_replay_checked") is True
                   and is_digest(raw_hash) and is_digest(rec.get("harbor_task_checksum")))
        if settled:
            task_checksums.add(rec["harbor_task_checksum"])
        seen[scenario] = (state if settled else "unresolved", known)
    matched = len(task_checksums) == 1
    complete = matched and len(seen) == len(SCENARIOS) and all(
        state in ("pass", "fail") for state, _ in seen.values())
    rows = []
    total = 0
    known_count = 0
    for scenario in SCENARIOS:
        state, known = seen.get(scenario, ("missing", None))
        if known is not None:
            total += _units(known)
            known_count += 1
        rows.append({"scenario": scenario, "state": state, "known_fictional_usd": known,
                     "fictional_cost_per_completion_usd": known if complete and state == "pass" else None})
    return {"schema_version": 1, "scope": plan["scope"], "plan_sha256": plan["plan_sha256"],
            "complete_matched_accounting": complete, "eligible_for_ranking": False,
            "provider_invoice_reconciled": False, "real_provider_expenditure": False,
            "task_checksums_consistent": matched,
            "known_cost_records": known_count,
            "known_fictional_total_usd": _usd(total) if known_count else None, "rows": rows}


def render_comparison(plan: dict, observations: list[dict]) -> str:
    """Generate an offline report from observations, not a saved summary."""
    report = summarize_comparison(plan, observations)
    def money(value, fallback="Unavailable"):
        return "$" + escape(value) if value is not None else fallback
    rows = "".join(
        "<tr><th scope='row'>" + escape(r["scenario"]) + "</th><td>" + escape(r["state"])
        + "</td><td>" + money(r["known_fictional_usd"]) + "</td><td>"
        + money(r["fictional_cost_per_completion_usd"],
                "Undefined (zero passes)" if report["complete_matched_accounting"] and r["state"] == "fail"
                else "Withheld") + "</td></tr>" for r in report["rows"])
    status = "Complete matched accounting" if report["complete_matched_accounting"] else "Incomplete accounting — ratios withheld"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Fictional repository comparison · Cost to Done</title>
<style>body{{margin:0;background:#f7f7f5;color:#171717;font:16px/1.6 system-ui,sans-serif}}main{{max-width:960px;padding:40px 24px;margin:auto}}h1{{font-size:clamp(30px,5vw,54px);line-height:1.1}}small{{text-transform:uppercase;letter-spacing:.08em;font-weight:700}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:650px}}th,td{{text-align:left;padding:16px 12px;border-bottom:1px solid #bbb;font-variant-numeric:tabular-nums}}code{{overflow-wrap:anywhere}}footer{{margin-top:36px;border-top:1px solid #bbb;padding-top:16px}}</style></head>
<body><main><small>Fictional provider · scripted integration test · no model ranking</small>
<h1>Compare the cost of completing work.</h1><p>{status}. Both scenarios use the same prepared repository, acceptance tests and rate card. The responses and prices are fictional.</p>
<p>Known fictional expenditure: <strong>{money(report["known_fictional_total_usd"])}</strong> ({report["known_cost_records"]}/2 cost records). Missing expenditure is not zero.</p>
<div class="scroll" role="region" aria-label="Matched fictional observations" tabindex="0"><table><thead><tr><th>Scripted scenario</th><th>Verifier outcome</th><th>Fictional cost</th><th>Cost / completion</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>Prepared task digest: <code>{escape(plan["task_input_sha256"])}</code></p><p>Frozen plan digest: <code>{escape(plan["plan_sha256"])}</code></p>
<footer>No real provider inference, invoices, external scripts or independent adversarial verifier guarantees.</footer></main></body></html>"""


def read_comparison(directory: Path) -> tuple[dict, list[dict]]:
    """Read bounded exact evidence filenames; ignore derived reports."""
    if directory.is_symlink() or not directory.is_dir():
        raise ReceiptError("comparison directory must be a real directory")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ReceiptError("duplicate comparison JSON field")
            result[k] = v
        return result
    def read(path):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256_000:
            raise ReceiptError("unsafe comparison evidence file")
        return json.loads(path.read_bytes(), object_pairs_hook=unique)
    plan = read(directory / "plan.json")
    rows = []
    for path in sorted(directory.glob("*.json")):
        if path.name in ("plan.json", "summary.json"):
            continue
        if path.stem not in SCENARIOS:
            raise ReceiptError("unexpected comparison evidence filename")
        rec = read(path)
        if not isinstance(rec, dict) or rec.get("scenario") != path.stem:
            raise ReceiptError("comparison filename identity mismatch")
        rows.append(rec)
    return plan, rows


def write_comparison(directory: Path, output: Path) -> None:
    plan, records = read_comparison(directory)
    publish_private_texts([(output, render_comparison(plan, records))])
