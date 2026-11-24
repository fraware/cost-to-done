"""Create a fixed synthetic Git repository and exact prepared task pair."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cost_to_done.repository_pilot import NAME, STARTER, REFERENCE, TEST, INSTRUCTION, validate_fixed_starter
from cost_to_done.repository_task import prepare_repository_task


def main() -> int:
    root = Path(sys.argv[1]).resolve(strict=True)
    repo = root / "pilot-repo"
    repo.mkdir()
    def git(*args):
        env = dict(os.environ)
        env.update(GIT_AUTHOR_DATE="2026-11-23T00:00:00Z",
                   GIT_COMMITTER_DATE="2026-11-23T00:00:00Z")
        subprocess.run(["git", "-C", str(repo), *args], env=env, check=True)
    git("init", "-q", "--object-format=sha1")
    git("config", "user.name", "Cost to Done fixture")
    git("config", "user.email", "fixture@example.invalid")
    (repo / "app").mkdir()
    (repo / "acceptance").mkdir()
    (repo / "acceptance/test_calc.py").write_bytes(TEST)
    instruction = root / "pilot-instruction.md"
    instruction.write_bytes(INSTRUCTION)
    for name, source in (("pilot-starter", STARTER), ("pilot-reference", REFERENCE)):
        (repo / "app/calc.py").write_bytes(source)
        git("add", "app/calc.py", "acceptance/test_calc.py")
        git("commit", "-qm", name)
        prepare_repository_task(repo, revision="HEAD", name=NAME,
                                sources=["app/calc.py"], tests=["acceptance/test_calc.py"],
                                instruction=instruction, output=root / name)
    validate_fixed_starter(root / "pilot-starter")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
