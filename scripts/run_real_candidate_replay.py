"""Bounded, separately identified real-provider candidate replay qualification."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.live import LiveConfig, execute_live
from cost_to_done.panel import CONFIGURATIONS
from cost_to_done.private_files import publish_private_texts
from cost_to_done.replay import captured_candidate, replay_candidate
from scripts.run_real_model_smoke import attestation


def replay_record(root: Path, outcome: dict, model: str) -> dict:
    """Retain financial observations even when candidate replay fails."""
    record = attestation(outcome, model)
    record.update(schema_version=3, cohort="frontier-allocation-candidate-replay-v1",
                  candidate_capture_requested=True, candidate_replay=None,
                  replay_status="unavailable", harbor_replay_agreement=None)
    if outcome.get("candidate_capture_requested") is not True:
        return record
    expected = record.get("harbor_raw_result_sha256")
    job = outcome.get("private_job_dir")
    if not isinstance(expected, str) or not isinstance(job, str):
        return record
    try:
        candidate = captured_candidate(Path(job), "allocation-repair",
                                       expected_result_sha256=expected)
        replay = replay_candidate(root, "allocation-repair", candidate)
    except (ReceiptError, OSError, ValueError):
        return record
    record["candidate_replay"] = replay
    record["replay_status"] = replay["outcome"]
    executed = replay["independent_process_reexecution"] is True
    record["verifier_independently_reexecuted"] = executed
    record["harbor_replay_agreement"] = (
        replay["outcome"] == record["harbor_trial_outcome"] if executed else None)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--configuration", choices=tuple(CONFIGURATIONS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (os.environ.get("GITHUB_ACTIONS") != "true"
            or os.environ.get("GITHUB_REPOSITORY") != "fraware/cost-to-done"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or os.environ.get("CTD_REPLAY_AUTHORIZED") != "1"):
        raise SystemExit("trusted first-attempt replay authorization missing")
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("replay output already exists")
    root = args.repo_root.resolve(strict=True)
    model, schedule = CONFIGURATIONS[args.configuration]
    key = os.environ.pop("CTD_OPENAI_SECRET", "")
    if not key:
        raise SystemExit("provider credential unavailable")
    with tempfile.TemporaryDirectory(dir=os.environ.get("RUNNER_TEMP")) as directory:
        secret = Path(directory) / "upstream.key"
        fd = os.open(secret, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(key)
        del key
        config = LiveConfig(root, root / "tasks/allocation-repair",
                            root / "runs/real-candidate-replay", model,
                            root / schedule, secret, "1", "replay-" + args.configuration,
                            5, 900, "responses", "low", capture_candidate=True)
        try:
            outcome = execute_live(config, acknowledged=True)
        except (ReceiptError, OSError, ValueError):
            outcome = {"status": "incomplete_or_uncertain", "api": "responses",
                       "reasoning_effort": "low", "task_fixture": "allocation-repair"}
    # The real provider credential file has been deleted before replay starts.
    record = replay_record(root, outcome, model)
    publish_private_texts([(args.output, json.dumps(record, sort_keys=True, indent=2,
                                                    allow_nan=False) + "\n")])
    print(json.dumps(record, sort_keys=True, indent=2, allow_nan=False))
    return 0 if (record["trial_status"] == "completed_with_unverified_rate_card_estimate"
                 and record["harbor_replay_agreement"] is True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
