"""Mock-only qualification of Harbor final-source export and fresh verification."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cost_to_done import live
from cost_to_done.replay import captured_candidate, replay_candidate
from cost_to_done.private_files import publish_private_texts
from scripts.run_live_rehearsal import run
from scripts.check_live_rehearsal import check


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: rehearse_candidate_replay ROOT OUTPUT_DIR FAKE_KEY_FILE")
    root, output, key = (Path(x).resolve() for x in sys.argv[1:])
    task = os.environ.get("CTD_REHEARSAL_TASK", "allocation-repair")
    module = live.TRUSTED_TASK_MODULES[task]
    # Use the production opt-in staging path and the fictional credential gate.
    run(root, output, key, capture_candidate=True)
    harbor_check = check(output)
    candidate = captured_candidate(output / "rehearsal-scripted", task,
                                   expected_result_sha256=harbor_check["harbor_trial_sha256"])
    positive = replay_candidate(root, task, candidate)
    negative = replay_candidate(root, task, root / "tasks" / task / "environment" / module)
    report = {"scope": "mock_only", "harbor_trial_sha256": harbor_check["harbor_trial_sha256"],
              "candidate_replay": positive, "unchanged_starter_replay": negative}
    payload = json.dumps(report, sort_keys=True, indent=2) + "\n"
    publish_private_texts([(output / "candidate-replay.json", payload)])
    print(payload, end="")
    if positive["outcome"] != "pass" or negative["outcome"] != "fail":
        raise RuntimeError("fresh candidate replay or negative control did not agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
