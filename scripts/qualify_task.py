"""Qualify a bundled single-module trusted repair task without containers.

Runs the unchanged starter and the withheld reference in *separate temporary
worktrees*. This is a local verifier check, not a Harbor run or a security
sandbox; never run this command on untrusted downloaded tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return a content digest for an ordinary local file."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"not a regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_verifier(worktree: Path, tests: Path) -> subprocess.CompletedProcess[str]:
    """Run the Python standard-library acceptance tests against one worktree."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(worktree)
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-p", "test_*.py", "-v"],
        cwd=worktree,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def qualify(task: Path) -> dict[str, object]:
    """Ensure the baseline fails and the reference passes independently."""
    task = task.resolve(strict=True)
    starters = sorted((task / "environment").glob("*.py"))
    if len(starters) != 1:
        raise ValueError("expected exactly one Python starter module")
    starter = starters[0]
    tests = task / "tests" / "test_state.py"
    solution = task / "solution" / "solve.sh"
    for file in (starter, tests, solution):
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"missing or symlinked task artifact: {file}")
    with tempfile.TemporaryDirectory(prefix="cost-to-done-qualify-") as scratch:
        first = Path(scratch) / "baseline"
        second = Path(scratch) / "reference"
        first.mkdir()
        second.mkdir()
        shutil.copyfile(starter, first / starter.name)
        shutil.copyfile(starter, second / starter.name)
        baseline = run_verifier(first, task / "tests")
        if baseline.returncode == 0:
            raise RuntimeError("qualification failed: unchanged starter unexpectedly passed")
        env = dict(os.environ)
        env["APP_ROOT"] = str(second)
        solve = subprocess.run(
            ["bash", str(solution)], env=env, capture_output=True, text=True,
            timeout=30, check=False,
        )
        if solve.returncode != 0:
            raise RuntimeError(f"reference solve.sh failed: {solve.stderr}")
        reference = run_verifier(second, task / "tests")
        if reference.returncode != 0:
            raise RuntimeError(f"reference verification failed:\n{reference.stdout}\n{reference.stderr}")
    return {
        "qualification": "local-trusted-control",
        "baseline": "fail",
        "reference": "pass",
        "task": task.name,
        "starter_sha256": sha256_file(starter),
        "verifier_sha256": sha256_file(tests),
        "oracle_script_sha256": sha256_file(solution),
        "scope": "verifier logic qualification; no model or Harbor execution",
    }


def main() -> int:
    """Print JSON evidence; fail closed on any qualification error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", type=Path, default=Path("tasks/allocation-repair"))
    parser.add_argument("--output", type=Path, help="optional new JSON artifact path")
    args = parser.parse_args()
    try:
        evidence = qualify(args.task)
        output = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output)
        print(output, end="")
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"qualification error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
