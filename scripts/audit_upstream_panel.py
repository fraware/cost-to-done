"""Review an extracted upstream panel artifact offline; never invoke a provider.

Recompute qualification bindings, intent coverage and failure-inclusive
accounting from original redacted records, not from the saved summary.
This checks content consistency, not execution authenticity or invoices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any

from cost_to_done.core import ReceiptError
from cost_to_done.ledger import _units, _usd
from cost_to_done.private_files import publish_private_texts
from cost_to_done.upstream_pilot import STARTERS, MODELS, ALLOWANCE
from scripts.run_upstream_pilot import validate_plan, SCOPE
from scripts.prepare_external_controls import CASES
from cost_to_done.upstream_replay import MODULES
from cost_to_done.replay import IMAGE, REPLAY_SCRIPT

HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE = 2_000_000


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def read(root: Path, path: Path) -> dict:
    if (not path.is_relative_to(root) or path.resolve() != path or path.is_symlink()
            or not path.is_file() or path.stat().st_size > MAX_FILE):
        raise ReceiptError(f"missing or unsafe evidence file: {path.name}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReceiptError("duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ReceiptError(f"invalid JSON constant: {value}")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ReceiptError("oversized evidence file")
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ReceiptError("evidence must be a JSON object")
    return result


def audit_qualifications(root: Path, plan: dict) -> None:
    """Check recorded no-model controls and their linkage to the plan."""
    seen_raw = set()
    for task, pin in STARTERS.items():
        base = root / "upstream-controls" / task
        q = read(root, base / "qualification.json")
        p = read(root, base / "provenance.json")
        qdigest = digest({k: v for k, v in q.items() if k != "qualification_sha256"})
        if (q.get("qualification_sha256") != qdigest
                or qdigest != plan["qualification_digests"][task]
                or type(q.get("schema_version")) is not int or q["schema_version"] != 1
                or q.get("status") != "repository_task_controls_agree"
                or q.get("scope") != "operator_supplied_local_harbor_nop_controls"
                or q.get("task") != task or q.get("origin_authenticated") is not False
                or q.get("paid_execution_authorized") is not False
                or type(q.get("provider_calls")) is not int or q["provider_calls"] != 0
                or not is_digest(q.get("shared_input_sha256"))
                or p.get("scope") != "public_upstream_development_controls"
                or p.get("task") != task or p.get("held_out") is not False
                or p.get("upstream_repository") != "https://github.com/python/cpython"
                or p.get("upstream_issue") != CASES[task]["issue"]
                or p.get("source_path") != f"Lib/{CASES[task]['module']}.py"
                or type(p.get("provider_calls")) is not int or p["provider_calls"] != 0
                or p.get("paid_execution_authorized") is not False):
            raise ReceiptError("qualification or provenance scope mismatch")
        controls = p.get("controls")
        if not isinstance(controls, dict) or set(controls) != {"starter", "reference"}:
            raise ReceiptError("missing local controls")
        for role, expected in (("starter", "fail"), ("reference", "pass")):
            row, source = q.get(role), controls[role]
            if not isinstance(row, dict) or not isinstance(source, dict):
                raise ReceiptError("invalid qualification control")
            local = source.get("local_control")
            raw = row.get("harbor_raw_result_sha256")
            if (row.get("outcome") != expected or not is_digest(raw) or raw in seen_raw
                    or not is_digest(row.get("harbor_task_checksum"))
                    or not is_digest(row.get("task_input_sha256"))
                    or row["task_input_sha256"] != source.get("task_input_sha256")
                    or row.get("git_commit") != source.get("packaging_commit")
                    or not re.fullmatch(r"[0-9a-f]{40}", str(row.get("git_commit")))
                    or (source.get("upstream_commit"), source.get("upstream_source_blob")) != CASES[task][role]
                    or source.get("upstream_license_blob") != CASES[task]["license"]
                    or not is_digest(source.get("source_sha256"))
                    or not isinstance(local, dict) or local.get("outcome") != expected
                    or type(local.get("tests")) is not int or local["tests"] != 4
                    or any(type(local.get(k)) is not int or local[k] != 0 for k in
                           ("errors", "skips", "expected_failures", "unexpected_successes"))
                    or type(local.get("failures")) is not int
                    or not 0 <= local["failures"] <= 4
                    or (local["failures"] > 0) != (role == "starter")):
                raise ReceiptError("control identity or outcome mismatch")
            seen_raw.add(raw)
        if (q["starter"]["task_input_sha256"] != pin
                or q["starter"]["task_input_sha256"] == q["reference"]["task_input_sha256"]
                or q["starter"]["git_commit"] == q["reference"]["git_commit"]
                or q["starter"]["harbor_task_checksum"] == q["reference"]["harbor_task_checksum"]):
            raise ReceiptError("invalid starter/reference support")


def audit(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ReceiptError("artifact root must be a real directory")
    root = root.resolve(strict=True)
    preflight = root / "upstream-preflight"
    plan = read(root, preflight / "plan.json")
    validate_plan(plan)
    preview = read(root, preflight / "preflight.json")
    if (preview != {"scope": SCOPE, "plan_sha256": plan["plan_sha256"],
                    "staged_trials": 16, "provider_calls": 0,
                    "paid_execution_authorized": False}
            or type(preview["staged_trials"]) is not int
            or type(preview["provider_calls"]) is not int
            or preview["paid_execution_authorized"] is not False):
        raise ReceiptError("unexpected preflight declaration")
    audit_qualifications(root, plan)
    capture = plan.get("schema_version") == 2
    paid = root / "upstream-paid"
    paid_present = paid.exists() or paid.is_symlink()
    filenames = set()
    if paid_present:
        if paid.is_symlink() or not paid.is_dir() or paid.resolve() != paid:
            raise ReceiptError("unsafe paid evidence directory")
        filenames = {path.name for path in paid.iterdir()}
        allowed = {"plan.json", "summary.json"} | {
            f"{i:02d}{suffix}.json" for i in range(16) for suffix in (("", ".intent", ".replay") if capture else ("", ".intent"))}
        if filenames - allowed or read(root, paid / "plan.json") != plan:
            raise ReceiptError("unexpected paid evidence or changed plan")
        # The archived derived summary is intentionally ignored.
    seen_raw = set()
    checksums = {task: set() for task in STARTERS}
    details = []
    stopped = False
    for index, trial in enumerate(plan["trials"]):
        ident, task, model = trial["id"], trial["task"], trial["model"]
        intent_name, record_name = f"{index:02d}.intent.json", f"{index:02d}.json"
        has_intent, has_record = intent_name in filenames, record_name in filenames
        replay_name = f"{index:02d}.replay.json"
        has_replay = replay_name in filenames
        if has_replay and not has_record:
            raise ReceiptError("replay without original trial observation")
        if has_record and not has_intent or stopped and (has_intent or has_record):
            raise ReceiptError("non-prefix execution or observation without intent")
        state, cost = "not_observed", None
        replay_state = "not_requested" if not capture else "not_observed"
        if has_intent:
            intent = read(root, paid / intent_name)
            if intent != {"trial_id": ident, "plan_sha256": plan["plan_sha256"],
                          "status": "attempt_intended"}:
                raise ReceiptError("intent identity mismatch")
            state = "intent_without_observation"
        if has_record:
            record = read(root, paid / record_name)
            if (record.get("trial_id") != ident or record.get("model") != model
                    or record.get("scope") != SCOPE
                    or record.get("plan_sha256") != plan["plan_sha256"]
                    or record.get("task_input_sha256") != STARTERS[task]
                    or record.get("qualification_sha256") != plan["qualification_digests"][task]
                    or record.get("mock_only") is not False
                    or record.get("provider_invoice_reconciled") is not False
                    or record.get("provider_spend_limit_verified") is not False
                    or record.get("verifier_independently_reexecuted") is not False):
                raise ReceiptError("observation identity or disclosure mismatch")
            raw = record.get("harbor_raw_result_sha256")
            if raw is not None:
                if not is_digest(raw) or raw in seen_raw:
                    raise ReceiptError("invalid or duplicate raw result identity")
                seen_raw.add(raw)
            cost = record.get("gateway_rate_card_estimate_usd")
            if cost is not None:
                if record.get("ledger_observed") is not True:
                    raise ReceiptError("cost present without observed ledger")
                cost = _usd(_units(cost))
            outcome = record.get("harbor_trial_outcome")
            checksum = record.get("harbor_task_checksum")
            settled = (record.get("trial_status") == "completed_with_unverified_rate_card_estimate"
                       and record.get("repository_execution_scope") == "fixed_public_upstream_pilot"
                       and record.get("price_schedule_sha256") == plan["price_schedule_digests"][model]
                       and record.get("api") == plan["api"]
                       and record.get("reasoning_effort") == plan["reasoning_effort"]
                       and record.get("ledger_observed") is True
                       and record.get("gateway_breached") is False
                       and all(type(record.get(k)) is int and record[k] == 0
                               for k in ("gateway_pending", "gateway_uncertain"))
                       and type(record.get("gateway_recorded_calls")) is int
                       and record["gateway_recorded_calls"] > 0
                       and cost is not None and 0 < _units(cost) <= _units(ALLOWANCE)
                       and is_digest(checksum) and is_digest(raw) and outcome in ("pass", "fail"))
            state = outcome if settled else "unresolved"
            if settled:
                checksums[task].add(checksum)
                if len(checksums[task]) != 1:
                    state = "unresolved"
        if capture and state in ("pass", "fail"):
            replay_state = "missing"
            if has_replay:
                side = read(root, paid / replay_name)
                if (set(side) != {"trial_id", "plan_sha256", "replay", "agreement"}
                        or side["trial_id"] != ident
                        or side["plan_sha256"] != plan["plan_sha256"]):
                    raise ReceiptError("replay sidecar identity mismatch")
                replay = side["replay"]
                if replay is None:
                    if side["agreement"] is not None:
                        raise ReceiptError("agreement without replay observation")
                    replay_state = "unresolved"
                else:
                    if not isinstance(replay, dict):
                        raise ReceiptError("invalid replay observation")
                    expected_test = hashlib.sha256(CASES[task]["tests"].encode()).hexdigest()
                    expected_script = hashlib.sha256(REPLAY_SCRIPT.replace(
                        "test_state.py", "test_regression.py").encode()).hexdigest()
                    if (replay.get("task") != task or replay.get("source_path") != MODULES[task]
                            or replay.get("base_task_input_sha256") != STARTERS[task]
                            or replay.get("harbor_raw_result_sha256") != raw
                            or replay.get("verifier_sha256") != expected_test
                            or replay.get("replay_script_sha256") != expected_script
                            or replay.get("image") != IMAGE
                            or replay.get("network_mode") != "none"
                            or replay.get("provider_credentials_mounted") is not False
                            or replay.get("adversarial_verifier_integrity_established") is not False
                            or not is_digest(replay.get("candidate_sha256"))):
                        raise ReceiptError("replay binding or scope mismatch")
                    replay_outcome = replay.get("outcome")
                    executed = replay.get("independent_process_reexecution")
                    if executed is True:
                        if (replay.get("cleanup_confirmed") is not True
                                or replay_outcome not in ("pass", "fail")
                                or side["agreement"] is not (replay_outcome == state)):
                            raise ReceiptError("inconsistent replay verdict")
                        replay_state = "agree" if side["agreement"] else "disagree"
                    elif executed is False and replay_outcome == "unresolved" and side["agreement"] is None:
                        replay_state = "unresolved"
                    else:
                        raise ReceiptError("invalid replay execution status")
        elif has_replay:
            raise ReceiptError("replay recorded for an unresolved original trial")
        if state not in ("pass", "fail") or capture and replay_state != "agree":
            stopped = True
        details.append({**trial, "state": state, "known_estimate_usd": cost,
                        "replay_state": replay_state})
    complete = (all(row["state"] in ("pass", "fail") for row in details)
                and all(len(x) == 1 for x in checksums.values()))
    replay_complete = capture and complete and all(r["replay_state"] == "agree" for r in details)
    summaries = []
    for model in sorted(MODELS):
        rows = [row for row in details if row["model"] == model]
        counts = Counter(row["state"] for row in rows)
        costs = [_units(row["known_estimate_usd"]) for row in rows
                 if row["known_estimate_usd"] is not None]
        total = sum(costs)
        passes = counts["pass"]
        summaries.append({"model": model, "planned": len(rows), "passes": passes,
                          "failures": counts["fail"], "unresolved": counts["unresolved"],
                          "intent_without_observation": counts["intent_without_observation"],
                          "not_observed": counts["not_observed"], "known_cost_records": len(costs),
                          "known_estimate_usd": _usd(total) if costs else None,
                          "cost_per_completion": {"numerator_usd": _usd(total), "denominator": passes}
                          if complete and passes else None})
    return {"schema_version": 1, "scope": SCOPE, "plan_sha256": plan["plan_sha256"],
            "harness_commit": plan["harness_commit"], "qualification_records_checked": 4,
            "staged_trials": 16, "paid_artifact_present": paid_present,
            "complete_matched_accounting": complete, "provider_invoice_reconciled": False,
            "candidate_replay_required": capture, "complete_replay_agreement": replay_complete,
            "replay_agreement_count": sum(r["replay_state"] == "agree" for r in details),
            "execution_authenticated": False, "independent_verifier_replay": False,
            "held_out": False, "eligible_for_ranking": False,
            "configurations": summaries, "trials": details}


def render(report: dict) -> str:
    def money(amount):
        return "$" + escape(amount) if amount is not None else "Unavailable"
    def ratio(row):
        value = row["cost_per_completion"]
        if value is not None:
            return money(format(Decimal(value["numerator_usd"]) / value["denominator"], ".6f"))
        return "Undefined (zero passes)" if report["complete_matched_accounting"] else "Withheld"
    headings = ("Configuration", "Planned", "Pass", "Fail", "Unresolved", "Intent only",
                "Not observed", "Known costs", "Known estimate", "Estimate / completion")
    rows = []
    for r in report["configurations"]:
        cells = [r["model"], r["planned"], r["passes"], r["failures"], r["unresolved"],
                 r["intent_without_observation"], r["not_observed"], r["known_cost_records"]]
        rows.append("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in cells)
                    + f"<td>{money(r['known_estimate_usd'])}</td><td>{ratio(r)}</td></tr>")
    trials = "".join("<tr>" + "".join(f"<td>{escape(str(t[k]))}</td>" for k in
                                     ("task", "model", "repetition", "state", "replay_state"))
                     + f"<td>{money(t['known_estimate_usd'])}</td></tr>" for t in report["trials"])
    status = ("Complete matched accounting and replay agreement" if report["complete_replay_agreement"]
              else "Complete original-verifier accounting" if report["complete_matched_accounting"]
              else "Preflight only — no paid evidence supplied" if not report["paid_artifact_present"]
              else "Incomplete accounting — ratios withheld")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Upstream evidence review | Cost to Done</title>
<style>body{{margin:0;background:#fafaf9;color:#171717;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1160px;margin:auto;padding:40px 24px}}h1{{font-size:clamp(28px,5vw,44px);line-height:1.1}}.scroll{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:720px;font-variant-numeric:tabular-nums}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #ccc}}code{{overflow-wrap:anywhere}}</style></head>
<body><main><p>Cost to Done / Public development evidence</p><h1>{status}</h1>
<p>Four historical CPython tasks. Two configurations. Sixteen planned episodes. Recorded cost estimates are not invoices; missing expenditure is unknown.</p>
<div class="scroll" tabindex="0" role="region" aria-label="Configuration accounting"><table><thead><tr>{''.join(f'<th scope="col">{h}</th>' for h in headings)}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Every planned episode</h2><div class="scroll" tabindex="0" role="region" aria-label="Trial accounting"><table><thead><tr><th>Task</th><th>Model</th><th>Repeat</th><th>State</th><th>Replay</th><th>Known estimate</th></tr></thead><tbody>{trials}</tbody></table></div>
<p>Plan: <code>{escape(report['plan_sha256'])}</code></p>
<p>Offline content-consistency review of redacted records; no authenticated execution, billing reconciliation, private holdout or general model ranking. Replay agreement, when present, is a recorded fresh-process observation, not independently authenticated execution or adversarial verifier integrity.</p></main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--html", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.artifact)
        outputs = [(args.output, json.dumps(result, indent=2, sort_keys=True) + "\n")]
        if args.html is not None:
            outputs.append((args.html, render(result)))
        publish_private_texts(outputs)
    except (ReceiptError, ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
