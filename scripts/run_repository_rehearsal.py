"""Run the actual gateway against a qualified synthetic repository, no paid key."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.repository_task import validate_repository_task
from scripts.check_live_rehearsal import check


def main() -> int:
    root, task, qualification, outputs, key = (Path(x).resolve() for x in sys.argv[1:])
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CTD_REHEARSAL_ONLY") != "1":
        raise RuntimeError("CI-only repository rehearsal guard missing")
    if key.read_bytes().strip() != b"ctd-fake-upstream-key-for-tests-12345678":
        raise RuntimeError("repository rehearsal requires the exact fictional key")
    identity = validate_repository_task(task)
    config = LiveConfig(root, task, outputs, "test-model-1",
                        root / "tests/fixtures/mock-price-schedule.json", key,
                        "5", "rehearsal-scripted", 3, 900, "responses", "low",
                        repository_task_sha256=identity["task_input_sha256"],
                        repository_qualification=qualification)
    result = execute_live(config, acknowledged=True)
    if result["status"] != "completed_with_unverified_rate_card_estimate":
        raise RuntimeError("repository rehearsal did not complete cleanly")
    os.environ.update(CTD_REHEARSAL_TASK=task.name, CTD_REHEARSAL_API="responses",
                      CTD_REHEARSAL_REASONING="low")
    evidence = check(outputs)
    evidence.update(repository_task_sha256=identity["task_input_sha256"],
                    repository_execution_scope="mock_only")
    print(json.dumps(evidence, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
