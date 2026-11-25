"""Execute eight actual Harbor capture and isolated replay controls; no inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from cost_to_done.core import ReceiptError
from cost_to_done.harbor import inspect_harbor_job
from cost_to_done.private_files import publish_private_texts
from cost_to_done.upstream_pilot import STARTERS, validate_upstream_starter
from cost_to_done.upstream_replay import MODULES, stage_control, replay_upstream


def qualify(base: Path, name: str, output: Path) -> dict:
    starter = base / "starter"
    validate_upstream_starter(starter)
    provenance = json.loads((base / "provenance.json").read_bytes())
    output.mkdir(mode=0o700, exist_ok=False)
    rows = {}
    for role, expected in (("starter", "fail"), ("reference", "pass")):
        source = base / role
        staged = output / role
        binding = stage_control(source, staged)
        subprocess.run(["harbor", "run", "--path", str(staged), "--agent", "nop",
                        "--job-name", role, "--jobs-dir", str(output / "jobs"),
                        "--n-concurrent", "1", "--n-attempts", "1"],
                       check=True, timeout=480)
        job = output / "jobs" / role
        inspected = inspect_harbor_job(job)
        if inspected.get("complete") is not True or inspected.get("observed_trials") != 1:
            raise ReceiptError("capture control did not complete exactly one trial")
        trial = inspected["trials"][0]
        if (trial["agent"] != "nop" or trial["model"] is not None
                or trial["outcome"] != expected):
            raise ReceiptError("unexpected Harbor capture control result")
        replay = replay_upstream(starter, job, trial["raw_result_sha256"])
        original_hash = hashlib.sha256(
            (source / "environment/workspace" / MODULES[name]).read_bytes()).hexdigest()
        if (replay["outcome"] != expected or replay["independent_process_reexecution"] is not True
                or replay["cleanup_confirmed"] is not True
                or replay["candidate_sha256"] != original_hash
                or original_hash != provenance["controls"][role]["source_sha256"]):
            raise ReceiptError("capture or isolated replay control disagrees")
        rows[role] = {**binding, "harbor_outcome": expected,
                      "harbor_task_checksum": trial["task_checksum"], "replay": replay}
    return {"schema_version": 1, "scope": "public_upstream_nop_capture_replay_controls",
            "task": name, "provider_calls": 0, "held_out": False,
            "paid_execution_authorized": False, "controls": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("controls", type=Path)
    parser.add_argument("name", choices=tuple(STARTERS))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = qualify(args.controls.resolve() / args.name, args.name, args.output.resolve())
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    publish_private_texts([(args.output / "capture-replay.json", payload)])
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
