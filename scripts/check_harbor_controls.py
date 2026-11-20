"""Check measured Harbor nop/oracle controls without estimating costs.

Reads the raw trial result from each job. This command never infers model
success and deliberately does not output a monetary receipt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def control_result(job: Path, expected_agent: str, expected_reward: int) -> dict[str, str]:
    """Fail if a Harbor control job is incomplete, errored or misgraded."""
    files = sorted(job.glob("trials/*/result.json"))
    if len(files) != 1:
        raise ValueError(f"{job}: expected exactly one trial result, found {len(files)}")
    path = files[0]
    if path.is_symlink() or not path.resolve().is_relative_to(job.resolve()):
        raise ValueError(f"{path}: unsafe path")
    record: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError(f"{path}: expected a JSON object")
    info = record.get("agent_info")
    if not isinstance(info, dict) or info.get("name") != expected_agent:
        raise ValueError(f"{path}: expected agent {expected_agent}")
    if record.get("exception_info") or any(
        isinstance(step, dict) and step.get("exception_info")
        for step in (record.get("step_results") or [])
    ):
        raise ValueError(f"{path}: control ended in an exception")
    verifier = record.get("verifier_result")
    rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    if not isinstance(rewards, dict) or len(rewards) != 1:
        raise ValueError(f"{path}: missing/unexpected verifier rewards")
    observed = next(iter(rewards.values()))
    if type(observed) not in (int, float) or observed != expected_reward:
        raise ValueError(f"{path}: expected reward {expected_reward}, received {observed!r}")
    if not record.get("task_checksum") or not record.get("task_name"):
        raise ValueError(f"{path}: missing task identity")
    if not record.get("started_at") or not record.get("finished_at"):
        raise ValueError(f"{path}: missing timing identity")
    return {
        "agent": expected_agent,
        "reward": str(observed),
        "task_name": str(record["task_name"]),
        "task_checksum": str(record["task_checksum"]),
    }


def main() -> int:
    """Validate both control jobs and print a strict qualification summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nop", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    args = parser.parse_args()
    try:
        nop = control_result(args.nop, "nop", 0)
        oracle = control_result(args.oracle, "oracle", 1)
        if (nop["task_name"], nop["task_checksum"]) != (
            oracle["task_name"], oracle["task_checksum"]
        ):
            raise ValueError("controls used different task identities")
        print(json.dumps({"status": "qualified", "controls": [nop, oracle]}, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"control validation error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
