"""Qualify capture and fresh-process replay for exact public upstream tasks.

The only executable candidate support is the one pinned Python module per
task. The original acceptance tests are loaded from the validated starter,
not from candidate-controlled artifacts. No provider credentials are used
by the no-model qualification workflow.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .core import ReceiptError
from .repository_qualification import _manifest
from .replay import (
    MAX_CANDIDATE_BYTES, MAX_TEST_BYTES, _read_regular, captured_source,
    replay_source,
)
from .upstream_pilot import STARTERS, validate_upstream_starter

MODULES = {
    "cpython-statistics-92531": "Lib/statistics.py",
    "cpython-ipaddress-110196": "Lib/ipaddress.py",
    "cpython-fractions-119189": "Lib/fractions.py",
    "cpython-ipaddress-117566": "Lib/ipaddress.py",
}


def capture_declaration(task: Path, name: str) -> None:
    """Append only the known single-file artifact declaration."""
    module = MODULES.get(name)
    if module is None:
        raise ReceiptError("unknown upstream replay task")
    path = task / "task.toml"
    original = _read_regular(path, MAX_TEST_BYTES)
    if b"[[artifacts]]" in original:
        raise ReceiptError("candidate collection already declared")
    with path.open("ab") as stream:
        stream.write(f'\n[[artifacts]]\nsource = "/app/{module}"\ndestination = "candidate.py"\n'.encode())


def stage_control(source: Path, destination: Path) -> dict:
    """Copy validated control inputs, then add capture outside the base identity."""
    manifest = _manifest(source)
    name = manifest["task"]
    if name not in STARTERS:
        raise ReceiptError("unknown upstream replay control")
    destination.mkdir(mode=0o700)
    for relative in manifest["files"]:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(source / relative, target)
    capture_declaration(destination, name)
    return {"base_task_input_sha256": manifest["task_input_sha256"],
            "capture_task_toml_sha256": hashlib.sha256((destination / "task.toml").read_bytes()).hexdigest()}


def replay_upstream(starter: Path, job: Path, raw_result_sha256: str,
                    *, timeout: int = 45) -> dict:
    """Bind a collected source to the exact Harbor trial and pristine tests."""
    manifest = validate_upstream_starter(starter)
    name = manifest["task"]
    module = MODULES[name]
    candidate = captured_source(job, "/app/" + module,
                                expected_result_sha256=raw_result_sha256)
    source = _read_regular(candidate, MAX_CANDIDATE_BYTES)
    verifier = _read_regular(starter / "tests/test_regression.py", MAX_TEST_BYTES)
    if hashlib.sha256(verifier).hexdigest() != manifest["files"]["tests/test_regression.py"]["sha256"]:
        raise ReceiptError("pristine verifier digest changed")
    result = replay_source(name, module, source, "test_regression.py",
                           verifier, timeout=timeout)
    result.update(base_task_input_sha256=manifest["task_input_sha256"],
                  harbor_raw_result_sha256=raw_result_sha256,
                  source_path=module)
    return result
