"""Verify the original redacted panel ZIP against the frozen plan and log record.

No inference, Docker, provider credentials or execution of generated candidate
code. The historical checkout is independently reconstructed by CI. This checks
published observations and accounting, not provider invoices or raw grading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.panel_results import summarize_panel
from cost_to_done.panel_report import render_panel
from cost_to_done.private_files import publish_private_texts


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ReceiptError("duplicate JSON field in archived evidence")
        obj[key] = value
    return obj


def reject_constant(value: str):
    raise ReceiptError("nonfinite JSON")


def load_json(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def audit(archive: Path, historical_plan: dict, reference: dict) -> tuple[dict, dict, list[dict]]:
    """Read exact flat ZIP entries in memory; never extract paths to disk."""
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 10_000_000:
        raise ReceiptError("unsafe or oversized original ZIP")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != reference["github_reported_zip_sha256"]:
        raise ReceiptError("original ZIP SHA-256 mismatch")
    expected_ids = [x["trial_id"] for x in reference["observations"]]
    if len(expected_ids) != 18 or len(set(expected_ids)) != 18:
        raise ReceiptError("invalid log reference support")
    names = {"plan.json", "summary.json", *(tid + ".json" for tid in expected_ids)}
    data = {}
    with zipfile.ZipFile(archive) as zf:
        entries = zf.infolist()
        if len(entries) != len(names) or {x.filename for x in entries} != names:
            raise ReceiptError("unexpected or duplicate archive members")
        if sum(x.file_size for x in entries) > 4_000_000:
            raise ReceiptError("archive expansion exceeds limit")
        for item in entries:
            if (item.is_dir() or stat.S_ISLNK(item.external_attr >> 16)
                    or not 0 < item.file_size <= 2_000_000):
                raise ReceiptError("unsafe archive member")
            value = load_json(zf.read(item))
            if not isinstance(value, dict):
                raise ReceiptError("archive member must be an object")
            data[item.filename] = value
    plan = data["plan.json"]
    if plan != historical_plan or plan.get("plan_sha256") != reference["plan_sha256"]:
        raise ReceiptError("archived plan differs from pinned historical plan")
    if [x["trial_id"] for x in plan["trials"]] != expected_ids:
        raise ReceiptError("actual job log order differs from historical plan")
    records = []
    for expected in reference["observations"]:
        record = data[expected["trial_id"] + ".json"]
        if (record.get("trial_id") != expected["trial_id"]
                or record.get("trial_status") != expected["status"]
                or record.get("harbor_trial_outcome") != expected["verifier"]
                or record.get("gateway_rate_card_estimate_usd") != expected["rate_card_estimate_usd"]):
            raise ReceiptError("archived observation differs from completed log")
        records.append(record)
    summary = summarize_panel(plan, records)
    if summary != data["summary.json"] or not summary["complete_matched_accounting"]:
        raise ReceiptError("independent accounting does not match archived summary")
    result = {"schema_version": 1, "status": "original_redacted_archive_verified",
              "source_commit": reference["source_commit"], "workflow_run_id": reference["workflow_run_id"],
              "artifact_id": reference["artifact_id"], "zip_sha256": reference["github_reported_zip_sha256"],
              "historical_plan_reconstructed": True, "log_observations_matched": len(records),
              "archived_summary_recomputed": True, "provider_invoice_reconciled": False,
              "verifier_independently_reexecuted": False, "summary": summary}
    return result, plan, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--historical-plan", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result, plan, records = audit(args.archive, load_json(args.historical_plan.read_bytes()),
                                  load_json(args.reference.read_bytes()))
    args.output.mkdir(parents=True, exist_ok=False)
    publish_private_texts([(args.output / "archive-audit.json",
                            json.dumps(result, sort_keys=True, indent=2) + "\n"),
                           (args.output / "panel-report.html", render_panel(plan, records))])
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
