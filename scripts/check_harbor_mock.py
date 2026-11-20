"""Reject a mock Harbor agent smoke run without a complete trial and verifier.

No mock usages in this check are asserted to be real provider charges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cost_to_done.harbor import inspect_harbor_job


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_harbor_mock.py JOB_DIR")
    result = inspect_harbor_job(Path(sys.argv[1]))
    assert result["observed_trials"] == 1, result
    assert result["complete"] is True, result
    trial = result["trials"][0]
    assert trial["agent"] == "pi", trial
    assert trial["model"] == "test-model-1", trial
    assert trial["outcome"] == "fail", trial
    print(json.dumps({"status": "mock-harbor-trial-complete", "verifier_reward": 0,
                      "model": trial["model"], "agent": trial["agent"],
                      "billing_verified": False, "model_is_mock": True,
                      "verifier_artifact_sha256": trial.get("raw_result_sha256")}, indent=2))


if __name__ == "__main__":
    main()
