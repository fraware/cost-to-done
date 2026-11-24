"""Fixed public external-repository pilot; never authorize arbitrary inputs.

The fixture is synthetic and disclosed. A successful pilot establishes
transport and accounting feasibility, not general model quality.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .core import ReceiptError

NAME = "addition-repair"
STARTER = b"def add(a, b): return a-b\n"
REFERENCE = b"def add(a, b): return a+b\n"
TEST = b"import unittest\nfrom app.calc import add\nclass TestAddition(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(3, 2), 5)\n"
INSTRUCTION = b"Repair addition in app/calc.py.\n"
MODELS = {
    "gpt-6.1-terra": "experiments/live/prices-gpt-6.1-terra-2026-11-23.json",
    "gpt-6.2-sol": "experiments/live/prices-gpt-6.2-sol-2026-11-23.json",
}


def trusted_dispatch() -> bool:
    """Only the explicitly dispatched first attempt on the canonical main."""
    return all(os.environ.get(key) == value for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "fraware/cost-to-done",
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1", "CTD_REPOSITORY_PILOT_AUTHORIZED": "1",
    }.items())


def validate_fixed_starter(task: Path) -> dict:
    """Match all task bytes and permissions, including the generated wrapper."""
    from .repository_qualification import _manifest
    from .repository_task import DOCKERFILE, TEST_SCRIPT, _task_toml
    manifest = _manifest(task)
    expected = {
        "instruction.md": (INSTRUCTION, False),
        "task.toml": (_task_toml(NAME).encode(), False),
        "environment/Dockerfile": (DOCKERFILE.encode(), False),
        "environment/workspace/app/calc.py": (STARTER, False),
        "tests/test_calc.py": (TEST, False),
        "tests/test.sh": (TEST_SCRIPT.encode(), True),
    }
    records = {path: {"sha256": hashlib.sha256(data).hexdigest(), "executable": executable}
               for path, (data, executable) in expected.items()}
    if manifest["task"] != NAME or manifest["files"] != records:
        raise ReceiptError("paid external pilot accepts only the fixed public synthetic starter")
    return manifest
