"""Prepare a narrowly scoped Python Harbor task from committed Git objects.

No checkout, source execution, dependency installation, or model requests.
Only explicitly selected tracked regular files enter the staged environment.
The operator must review those bytes for secrets, licensing and trustworthiness.
This is task packaging, not a general secure repository execution service.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Sequence

from .core import ReceiptError
from .replay import IMAGE

_NAME = re.compile(r"[a-z][a-z0-9-]{1,47}\Z")
_COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}\Z")
_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
MAX_FILES = 100
MAX_FILE = 1_000_000
MAX_TOTAL = 10_000_000
MAX_INSTRUCTION = 64_000
DOCKERFILE = f"FROM {IMAGE}\nWORKDIR /app\nCOPY workspace/ /app/\n"
TEST_SCRIPT = """#!/usr/bin/env bash
set -eu
mkdir -p /logs/verifier
cd /app
# This verifier executes trusted operator-provided Python acceptance tests.
# It does not establish adversarial test integrity.
if python3 -I -B -c '
import sys, unittest
sys.path.insert(0, "/app")
suite = unittest.defaultTestLoader.discover("/tests", pattern="test_*.py")
if suite.countTestCases() == 0:
    sys.exit(2)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
'; then
    printf '1\\n' > /logs/verifier/reward.txt
else
    status=$?
    if [ "$status" -ne 1 ]; then
        exit "$status"
    fi
    printf '0\\n' > /logs/verifier/reward.txt
fi
"""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _git(root: Path, *args: str) -> bytes:
    """Read local object data only; reject missing objects instead of fetching."""
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TMPDIR", "TEMP", "LANG")
           if k in os.environ}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    command = ["git", "--no-replace-objects", "--literal-pathspecs",
               "-c", "protocol.allow=never", "-C", str(root), *args]
    try:
        proc = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReceiptError("local Git object read unavailable") from exc
    if proc.returncode != 0:
        raise ReceiptError("local Git object read failed; no remote fetch was attempted")
    return proc.stdout


def _path(raw: str) -> str:
    if not isinstance(raw, str) or len(raw) > 240:
        raise ReceiptError("invalid repository path")
    parts = raw.split("/")
    if not parts or any(not _COMPONENT.fullmatch(part) for part in parts):
        raise ReceiptError("select explicit relative non-hidden Git paths only")
    if parts[-1].lower().endswith((".pem", ".key", ".p12", ".pfx")):
        raise ReceiptError("credential-like file suffix is not supported")
    return raw


def _blob(root: Path, commit: str, relative: str) -> tuple[bytes, bool, str]:
    """Use tree metadata and blob bytes; working-tree edits are irrelevant."""
    raw = _git(root, "ls-tree", "-z", commit, "--", relative)
    entries = raw.rstrip(b"\0").split(b"\0")
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise ReceiptError("selected path must identify exactly one committed file")
    header, path = entries[0].split(b"\t", 1)
    fields = header.decode("ascii").split(" ")
    if len(fields) != 3 or path.decode("utf-8") != relative:
        raise ReceiptError("unexpected Git tree metadata")
    mode, kind, oid = fields
    if mode not in ("100644", "100755") or kind != "blob" or not _OID.fullmatch(oid):
        raise ReceiptError("only committed regular files are supported (no symlinks or submodules)")
    size = int(_git(root, "cat-file", "-s", oid))
    if size < 0 or size > MAX_FILE:
        raise ReceiptError("selected committed file exceeds size limit")
    data = _git(root, "cat-file", "blob", oid)
    if len(data) != size:
        raise ReceiptError("Git blob size mismatch")
    if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
        raise ReceiptError("Git LFS pointers are not materialized")
    return data, mode == "100755", oid


def _task_toml(name: str) -> str:
    return f"""schema_version = "1.4"

[task]
name = "cost-to-done/{name}"
version = "0.1.0"
authors = []
keywords = ["python", "repository-task"]

[metadata]
author_name = "Local task operator"
difficulty = "unknown"
category = "programming"
tags = ["python", "repository-task"]

[verifier]
timeout_sec = 90.0

[agent]
timeout_sec = 240.0

[environment]
build_timeout_sec = 300.0
cpus = 1
memory_mb = 2048
storage_mb = 10240
gpus = 0
allow_internet = false
"""


def prepare_repository_task(repository: Path, *, revision: str, name: str,
                            sources: Sequence[str], tests: Sequence[str],
                            instruction: Path, output: Path) -> dict[str, Any]:
    """Build a private Harbor task from a commit and explicit file selections.

    The instruction is a separate trusted local UTF-8 document. Acceptance
    tests are not copied into the image build context. There is no oracle,
    no claim of test secrecy, and no dependency installation.
    """
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ReceiptError("task name must be 2–48 lowercase letters, digits or hyphens")
    if revision != "HEAD" and (not isinstance(revision, str) or not _OID.fullmatch(revision)):
        raise ReceiptError("revision must be HEAD or an exact full commit object ID")
    if repository.is_symlink() or not repository.is_dir():
        raise ReceiptError("repository must be a real local Git directory")
    root = repository.resolve(strict=True)
    if output.exists() or output.is_symlink():
        raise ReceiptError("task output must be new")
    if not sources or not tests or len(sources) + len(tests) > MAX_FILES:
        raise ReceiptError("select 1–100 total source and acceptance-test files, with both groups nonempty")
    source_paths = [_path(x) for x in sources]
    test_paths = [_path(x) for x in tests]
    if len(set(source_paths + test_paths)) != len(source_paths) + len(test_paths):
        raise ReceiptError("duplicate or overlapping source/test selection")
    basenames = [Path(x).name for x in test_paths]
    if len(set(basenames)) != len(basenames) or any(
            not re.fullmatch(r"test_[A-Za-z0-9_]+\.py", x) for x in basenames):
        raise ReceiptError("acceptance tests must have unique test_*.py basenames")
    if (instruction.is_symlink() or not instruction.is_file()
            or instruction.stat().st_size > MAX_INSTRUCTION):
        raise ReceiptError("instruction must be a regular bounded UTF-8 file")
    instructions = instruction.read_bytes()
    if not instructions.decode("utf-8").strip() or len(instructions) > MAX_INSTRUCTION:
        raise ReceiptError("empty or oversized instruction")
    commit = _git(root, "rev-parse", "--verify", revision + "^{commit}").decode("ascii").strip()
    if not _OID.fullmatch(commit) or (revision != "HEAD" and revision != commit):
        raise ReceiptError("revision did not identify the requested commit")
    staged: dict[str, tuple[bytes, bool]] = {
        "instruction.md": (instructions, False),
        "task.toml": (_task_toml(name).encode("utf-8"), False),
        "environment/Dockerfile": (DOCKERFILE.encode("utf-8"), False),
        "tests/test.sh": (TEST_SCRIPT.encode("utf-8"), True),
    }
    identities = []
    total = 0
    for role, paths in (("source", source_paths), ("test", test_paths)):
        for relative in sorted(paths):
            data, executable, oid = _blob(root, commit, relative)
            total += len(data)
            if total > MAX_TOTAL:
                raise ReceiptError("total selected committed bytes exceed limit")
            destination = ("environment/workspace/" + relative if role == "source"
                           else "tests/" + Path(relative).name)
            staged[destination] = (data, executable)
            identities.append({"repository_path": relative, "role": role,
                               "git_blob": oid, "staged_path": destination})
    manifest = {
        "schema_version": 1, "status": "prepared_unqualified_repository_task",
        "task": name, "git_commit": commit, "runtime_image": IMAGE,
        "scope": "stdlib_python_explicit_committed_files",
        "source_and_test_objects": identities,
        "files": {p: {"sha256": _sha(data), "executable": executable}
                  for p, (data, executable) in sorted(staged.items())},
        "provider_calls": 0, "paid_execution_authorized": False,
        "baseline_qualified": False, "reference_qualified": False,
        "secrets_reviewed": False, "adversarial_verifier_integrity_established": False,
    }
    manifest["task_input_sha256"] = _sha(_canonical(manifest))
    # Exclusive creation; no overwrite of existing tasks or worktrees.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        for relative, (data, executable) in staged.items():
            path = output / relative
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("xb") as stream:
                stream.write(data)
            path.chmod(0o700 if executable else 0o600)
        with (output / "ctd-task-manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        (output / "ctd-task-manifest.json").chmod(0o600)
    except BaseException:
        shutil.rmtree(output)
        raise
    return manifest
