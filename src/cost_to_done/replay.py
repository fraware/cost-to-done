"""Replay a captured single-module candidate against pristine bundled tests.

Generated code is untrusted: never import it into the host interpreter.
The replay uses a fresh restricted Docker container and only two input files.
This checks acceptance-test reproducibility, not resistance to a malicious
candidate manipulating the Python test process or a container escape.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .live import TRUSTED_TASK_MODULES, _ALLOWED_ENV

IMAGE = "python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0"
MAX_CANDIDATE_BYTES = 256_000
MAX_TEST_BYTES = 256_000
REPLAY_SCRIPT = (
    "import sys, unittest; "
    "sys.path.insert(0, '/candidate'); "
    "suite=unittest.defaultTestLoader.discover('/verifier', pattern='test_state.py'); "
    "assert suite.countTestCases() > 0; "
    "result=unittest.TextTestRunner(verbosity=0).run(suite); "
    "sys.exit(0 if result.wasSuccessful() else 1)"
)


def _read_regular(path: Path, limit: int) -> bytes:
    """Reject symlinks, directories, devices, FIFOs, and oversized inputs."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ReceiptError("candidate replay requires a POSIX host with no-follow file access")
    if path.resolve(strict=True) != path:
        raise ReceiptError("replay input must not traverse symlinks")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ReceiptError("replay input must be a bounded regular file")
        data = stream.read(limit + 1)
    if not data or len(data) > limit:
        raise ReceiptError("empty or oversized replay input")
    return data


def captured_candidate(job: Path, task: str) -> Path:
    """Resolve the single Harbor 0.27 artifact from its collection manifest."""
    module = TRUSTED_TASK_MODULES.get(task)
    if module is None:
        raise ReceiptError("unknown bundled task")
    if job.is_symlink() or not job.is_dir():
        raise ReceiptError("missing or unsafe Harbor job")
    root = job.resolve(strict=True)
    manifests = sorted(root.glob("*/artifacts/manifest.json"))
    if len(manifests) != 1:
        raise ReceiptError("expected one Harbor artifact manifest")
    manifest = manifests[0]
    entries = json.loads(_read_regular(manifest, MAX_TEST_BYTES))
    if not isinstance(entries, list):
        raise ReceiptError("invalid artifact manifest")
    matching = [x for x in entries if isinstance(x, dict)
                and x.get("destination") == "artifacts/candidate.py"]
    if len(matching) != 1:
        raise ReceiptError("missing or ambiguous candidate collection")
    entry = matching[0]
    if (entry.get("source") != "/app/" + module or entry.get("type") != "file"
            or entry.get("status") != "ok" or entry.get("service") not in (None, "main")):
        raise ReceiptError("candidate artifact was not collected from the expected module")
    path = manifest.parent / "candidate.py"
    _read_regular(path, MAX_CANDIDATE_BYTES)
    return path


def replay_candidate(root: Path, task: str, candidate: Path, *, timeout: int = 45) -> dict[str, Any]:
    """Run original tests in a new, offline, non-root container.

    Only the captured source and original test module are mounted. Runtime
    image must already exist locally. A timeout or Docker error is unresolved.
    Raw candidate-controlled stdout and stderr are deliberately not published.
    """
    module = TRUSTED_TASK_MODULES.get(task)
    if module is None:
        raise ReceiptError("unknown bundled task")
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ReceiptError("invalid replay timeout")
    if root.is_symlink():
        raise ReceiptError("unsafe repository root")
    root = root.resolve(strict=True)
    source = _read_regular(candidate.absolute(), MAX_CANDIDATE_BYTES)
    verifier = _read_regular(root / "tasks" / task / "tests/test_state.py", MAX_TEST_BYTES)
    environment = {k: os.environ[k] for k in _ALLOWED_ENV if k in os.environ}
    name = "ctd-replay-" + uuid.uuid4().hex
    outcome = "unresolved"
    cleanup_confirmed = False
    with tempfile.TemporaryDirectory(prefix="ctd-replay-") as directory:
        stage = Path(directory)
        for folder, filename, payload in (("candidate", module, source),
                                          ("verifier", "test_state.py", verifier)):
            dest = stage / folder
            dest.mkdir(mode=0o755)
            path = dest / filename
            path.write_bytes(payload)
            path.chmod(0o444)
        # Bind mounts reference only the two staged directories, never the repo,
        # provider key, Docker socket, home directory, or original trial logs.
        if "," in str(stage):
            raise ReceiptError("unsupported Docker bind source path")
        command = [
            "docker", "run", "--rm", "--name", name, "--pull", "never",
            "--network", "none", "--read-only", "--user", "65534:65534",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--pids-limit", "64", "--memory", "256m", "--memory-swap", "256m",
            "--cpus", "1", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--mount", f"type=bind,src={stage / 'candidate'},dst=/candidate,readonly",
            "--mount", f"type=bind,src={stage / 'verifier'},dst=/verifier,readonly",
            "--workdir", "/tmp", IMAGE, "python", "-I", "-B", "-c", REPLAY_SCRIPT,
        ]
        try:
            proc = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  check=False, timeout=timeout)
            if proc.returncode in (0, 1):
                outcome = "pass" if proc.returncode == 0 else "fail"
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            # A timed-out Docker client need not terminate the container.
            try:
                subprocess.run(["docker", "rm", "-f", name], env=environment,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False, timeout=15)
                check = subprocess.run(["docker", "ps", "-a", "--filter", "name=^/" + name + "$",
                                        "--format", "{{.Names}}"], env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       check=False, timeout=15)
                cleanup_confirmed = check.returncode == 0 and not check.stdout.strip()
            except (OSError, subprocess.TimeoutExpired):
                pass
    if not cleanup_confirmed:
        outcome = "unresolved"
    return {"schema_version": 1, "task": task, "outcome": outcome,
            "candidate_sha256": hashlib.sha256(source).hexdigest(),
            "verifier_sha256": hashlib.sha256(verifier).hexdigest(),
            "image": IMAGE, "replay_script_sha256": hashlib.sha256(REPLAY_SCRIPT.encode("utf-8")).hexdigest(),
            "cleanup_confirmed": cleanup_confirmed,
            "network_mode": "none", "provider_credentials_mounted": False,
            "independent_process_reexecution": outcome in ("pass", "fail"),
            "adversarial_verifier_integrity_established": False}
