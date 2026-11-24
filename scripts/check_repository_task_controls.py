"""Check actual no-model Harbor controls on two independently packaged commits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cost_to_done.harbor import inspect_harbor_job
from cost_to_done.repository_task import validate_repository_task


def check(root: Path) -> dict:
    rows = {}
    manifests = {}
    for name, expected in (("negative", "fail"), ("positive", "pass")):
        validate_repository_task(root / name)
        manifest = json.loads((root / name / "ctd-task-manifest.json").read_text())
        inspected = inspect_harbor_job(root / "controls" / name)
        if inspected.get("complete") is not True or inspected.get("observed_trials") != 1:
            raise RuntimeError("expected exactly one completed control")
        trial = inspected["trials"][0]
        if trial["agent"] != "nop" or trial["outcome"] != expected or trial["model"] is not None:
            raise RuntimeError("unexpected no-model control outcome")
        if manifest["provider_calls"] != 0:
            raise RuntimeError("packaging must not request inference")
        manifests[name] = manifest
        rows[name] = {"outcome": trial["outcome"], "git_commit": manifest["git_commit"],
                      "harbor_raw_result_sha256": trial["raw_result_sha256"],
                      "task_input_sha256": manifest["task_input_sha256"]}
    negative, positive = manifests["negative"], manifests["positive"]
    if negative["git_commit"] == positive["git_commit"]:
        raise RuntimeError("controls must come from distinct commits")
    if negative["files"]["tests/test_calc.py"] != positive["files"]["tests/test_calc.py"]:
        raise RuntimeError("controls must use identical acceptance tests")
    if negative["files"]["environment/workspace/app/calc.py"] == positive["files"]["environment/workspace/app/calc.py"]:
        raise RuntimeError("reference must change source")
    return {"status": "user_repository_packaging_controls_passed", "mock_repository": True,
            "provider_calls": 0, "identical_acceptance_tests": True, "controls": rows}


if __name__ == "__main__":
    print(json.dumps(check(Path(sys.argv[1])), sort_keys=True, indent=2))
