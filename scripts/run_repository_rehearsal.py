"""Run a matched two-scenario repository experiment with fictional inference."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cost_to_done.gateway import PriceSchedule
from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.repository_task import validate_repository_task
from cost_to_done.repository_qualification import check_qualification
from cost_to_done.repository_comparison import build_comparison_plan, summarize_comparison, render_comparison, SCENARIOS
from cost_to_done.private_files import publish_private_texts
from scripts.check_live_rehearsal import check


def payload(value: dict) -> str:
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: run_repository_rehearsal ROOT TASK QUALIFICATION OUTPUTS FAKE_KEY")
    root, task, qualification, outputs, key = (Path(x).resolve() for x in sys.argv[1:])
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CTD_REHEARSAL_ONLY") != "1":
        raise RuntimeError("CI-only repository rehearsal guard missing")
    if key.read_bytes().strip() != b"ctd-fake-upstream-key-for-tests-12345678":
        raise RuntimeError("repository rehearsal requires the exact fictional key")
    identity = validate_repository_task(task)
    task_digest = identity["task_input_sha256"]
    receipt = check_qualification(task, qualification, task_digest)
    schedule = root / "tests/fixtures/mock-price-schedule.json"
    plan = build_comparison_plan(task_digest, receipt["qualification_sha256"], PriceSchedule.load(schedule).digest)
    outputs.mkdir(mode=0o700, exist_ok=False)
    report_dir = outputs / "comparison"
    report_dir.mkdir(mode=0o700)
    publish_private_texts([(report_dir / "plan.json", payload(plan))])
    observations = []
    for scenario in SCENARIOS:
        config = LiveConfig(root, task, outputs / scenario, "test-model-1", schedule, key,
                            "5", "rehearsal-scripted", 3, 900, "responses", "low",
                            repository_task_sha256=task_digest, repository_qualification=qualification)
        os.environ["CTD_REPOSITORY_MOCK_SCENARIO"] = scenario
        expected = "fail" if scenario == "repository-addition-incorrect" else "pass"
        rec = {"scenario": scenario, "plan_sha256": plan["plan_sha256"],
               "repository_task_sha256": task_digest, "qualification_sha256": receipt["qualification_sha256"],
               "price_schedule_sha256": plan["price_schedule_sha256"], "model": "test-model-1",
               "api": "responses", "reasoning_effort": "low", "mock_only": True,
               "billing_verified": False, "repository_execution_scope": "mock_only",
               "status": "unresolved", "fictional_rate_card_usd": None}
        try:
            result = execute_live(config, acknowledged=True)
            rec["fictional_rate_card_usd"] = result.get("gateway_snapshot", {}).get("settled")
            if result["status"] == "completed_with_unverified_rate_card_estimate":
                rec.update(check(config.jobs_dir, expected_outcome=expected, expected_task=task.name,
                                 expected_api="responses", expected_effort="low"))
        except (AssertionError, OSError, ValueError, RuntimeError):
            # Preserve any known expenditure and the planned identity; never
            # present an absent or uncertain observation as a zero-cost failure.
            pass
        finally:
            os.environ.pop("CTD_REPOSITORY_MOCK_SCENARIO", None)
        publish_private_texts([(report_dir / (scenario + ".json"), payload(rec))])
        observations.append(rec)
        if rec["status"] != "isolated-live-runner-mock-verified":
            break
    summary = summarize_comparison(plan, observations)
    publish_private_texts([(report_dir / "summary.json", payload(summary)),
                           (report_dir / "comparison.html", render_comparison(plan, observations))])
    print(payload(summary), end="")
    return 0 if summary["complete_matched_accounting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
