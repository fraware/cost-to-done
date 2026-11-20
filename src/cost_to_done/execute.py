"""Single-trial Harbor launch with explicit approval and evidence preservation.

This module is an orchestration boundary, not a billing firewall. A wall-clock
limit cannot prevent charges already incurred or cancel detached remote calls.
All model invocations require an explicit acknowledgement of that limitation.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .harbor import inspect_harbor_job

HARBOR_VERSION = "0.26.0"
PI_VERSION = "0.85.1"
SUPPORTED_AGENTS = frozenset({"pi"})
MODEL_RE = re.compile(r"(?:openai|anthropic)/[a-zA-Z0-9][a-zA-Z0-9._:-]{0,120}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,62}\Z")
KEYS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
PROVIDER_HOST = {"openai": "api.openai.com", "anthropic": "api.anthropic.com"}
# Pi installs nvm, Node and its pinned npm package inside the Harbor environment.
SETUP_HOSTS = ("raw.githubusercontent.com", "github.com", "nodejs.org", "registry.npmjs.org")


@dataclass(frozen=True)
class Launch:
    """User-defined, one-task model execution configuration."""

    task: Path
    jobs_dir: Path
    model: str
    agent: str = "pi"
    job_name: str = "cost-to-done-smoke"
    max_wall_seconds: int = 900
    max_turns: int = 10

    def checked(self) -> "Launch":
        """Validate all inputs before interacting with Harbor or a provider."""
        if self.agent not in SUPPORTED_AGENTS:
            raise ReceiptError(f"agent must be one of {', '.join(sorted(SUPPORTED_AGENTS))}")
        if MODEL_RE.fullmatch(self.model) is None:
            raise ReceiptError("model must be an explicit openai/<id> or anthropic/<id> route")
        if NAME_RE.fullmatch(self.job_name) is None:
            raise ReceiptError("job-name must be lowercase letters, digits, hyphens (max 63)")
        if type(self.max_wall_seconds) is not int or not 60 <= self.max_wall_seconds <= 3600:
            raise ReceiptError("max-wall-seconds must be an integer in [60, 3600]")
        if type(self.max_turns) is not int or not 1 <= self.max_turns <= 30:
            raise ReceiptError("max-turns must be an integer in [1, 30]")
        task = self.task.resolve(strict=True)
        if not task.is_dir() or self.task.is_symlink():
            raise ReceiptError("task must be a real directory, not a symlink")
        required = ("task.toml", "instruction.md", "environment/Dockerfile", "tests/test.sh")
        for rel in required:
            path = task / rel
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(task):
                raise ReceiptError(f"task must contain a regular, confined {rel}")
        jobs_dir = self.jobs_dir.resolve(strict=False)
        if jobs_dir.is_relative_to(task) or task.is_relative_to(jobs_dir):
            raise ReceiptError("jobs-dir and task tree must be disjoint")
        if self.jobs_dir.is_symlink() or (jobs_dir.exists() and not jobs_dir.is_dir()):
            raise ReceiptError("jobs-dir must be a real directory, not a symlink")
        if (jobs_dir / self.job_name).exists() or (jobs_dir / self.job_name).is_symlink():
            raise ReceiptError("job already exists; never overwrite an evaluation")
        return Launch(task, jobs_dir, self.model, self.agent, self.job_name, self.max_wall_seconds, self.max_turns)

    def command(self) -> list[str]:
        """Construct a shell-free single-trial Harbor command."""
        return [
            "harbor", "run", "--path", str(self.task), "--agent", self.agent,
            "--model", self.model, "--job-name", self.job_name,
            "--jobs-dir", str(self.jobs_dir), "--n-concurrent", "1",
            "--n-attempts", "1", "--ak", f"version={PI_VERSION}",
            "--ak", f"max_turns={self.max_turns}",
            "--allow-agent-host", PROVIDER_HOST[self.model.split("/", 1)[0]],
        ] + [arg for host in SETUP_HOSTS for arg in ("--allow-environment-host", host)]


def _task_hash(task: Path) -> str:
    """Hash every task input (including verifier), excluding the oracle solution.

    File paths, permissions and bytes are covered. This is an identity digest,
    not a claim of test secrecy or execution integrity.
    """
    digest = hashlib.sha256()
    files = sorted(p for p in task.rglob("*") if p.is_file() or p.is_symlink())
    for file in files:
        rel = file.relative_to(task)
        if rel.parts[0] == "solution":
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(task):
            raise ReceiptError(f"unsafe task file: {rel}")
        if file.stat().st_size > 20_000_000:
            raise ReceiptError(f"oversized task file: {rel}")
        payload = file.read_bytes()
        digest.update(str(rel).encode("utf-8") + b"\0")
        digest.update((file.stat().st_mode & 0o111).to_bytes(2, "big"))
        digest.update(len(payload).to_bytes(8, "big") + payload)
    return digest.hexdigest()


def plan(launch: Launch) -> dict[str, Any]:
    """Create a no-spend, reproducible execution plan."""
    run = launch.checked()
    return {
        "status": "dry_run_only",
        "harbor_required_version": HARBOR_VERSION,
        "model": run.model,
        "agent": run.agent,
        "task_digest_sha256": _task_hash(run.task),
        "command": run.command(),
        "max_wall_seconds": run.max_wall_seconds,
        "max_turns": run.max_turns,
        "pi_agent_version": PI_VERSION,
        "max_dollar_spend_enforced": False,
        "network_policy": {
            "agent_provider_host": PROVIDER_HOST[run.model.split("/", 1)[0]],
            "environment_setup_hosts": list(SETUP_HOSTS),
            "limitations": "Host permissions are delegated to Harbor; their enforcement and setup behavior need an integration test.",
        },
        "credentials_required_env": KEYS[run.model.split("/", 1)[0]],
        "warning": "Wall-clock termination does not impose a monetary budget; provider-side limits are necessary.",
    }


def _check_prerequisites(launch: Launch) -> None:
    """Fail before model invocation if the exact supported runtime is absent."""
    try:
        version = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ReceiptError(f"Harbor is missing; install harbor=={HARBOR_VERSION} in Python 3.12+") from exc
    if version != HARBOR_VERSION:
        raise ReceiptError(f"Harbor {version} installed; expected {HARBOR_VERSION}")
    key_name = KEYS[launch.model.split("/", 1)[0]]
    if not os.environ.get(key_name):
        raise ReceiptError(f"missing {key_name}; supply it only in the local environment")
    try:
        probe = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                               capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReceiptError("Docker daemon is unavailable") from exc
    if probe.returncode:
        raise ReceiptError("Docker daemon is unavailable")


def _run_bounded(command: list[str], *, timeout: int, logfile: Path) -> int:
    """Run Harbor once; on timeout, terminate its process group as best effort.

    Detached containers, network calls and charges might outlive this process.
    Logs stay in a mode-0600 local file because they can contain sensitive data.
    """
    fd = os.open(logfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
            raise ReceiptError(
                "Harbor exceeded the wall-clock limit; child processes were terminated. "
                "Check for detached containers and ongoing provider charges."
            ) from exc


def execute(launch: Launch, *, acknowledged: bool = False) -> dict[str, Any]:
    """Start exactly one paid model trial and preserve the resulting raw evidence.

    The operator has to opt in explicitly and enforce a provider-side budget.
    No automated publication or model-to-model ranking is performed here.
    """
    run = launch.checked()
    if not acknowledged:
        raise ReceiptError("execution needs --acknowledge-no-dollar-cap and an external provider spending limit")
    if os.name != "posix":
        raise ReceiptError("execution currently supported on Linux/macOS only; dry-run works elsewhere")
    _check_prerequisites(run)
    run.jobs_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = run.jobs_dir / f".{run.job_name}.driver.log"
    output = run.jobs_dir / f"{run.job_name}.execution.json"
    if log.exists() or output.exists():
        raise ReceiptError("run metadata exists; choose a fresh job name")
    timestamp = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "schema_version": 1,
        "status": "started",
        "started_at": timestamp,
        "plan": plan(run),
        "billing_verified": False,
        "max_dollar_spend_enforced": False,
        "log_path": str(log),
    }
    try:
        code = _run_bounded(run.command(), timeout=run.max_wall_seconds, logfile=log)
        record["exit_code"] = code
        if code != 0:
            record["status"] = "harbor_error"
        else:
            inspection = inspect_harbor_job(run.jobs_dir / run.job_name)
            if inspection["observed_trials"] != 1 or inspection["complete"] is False:
                raise ReceiptError("Harbor job must contain exactly one completed trial")
            row = inspection["trials"][0]
            if row["agent"] != run.agent or row["model"] != run.model.split("/", 1)[1]:
                raise ReceiptError("Harbor trial identity differs from requested model/agent")
            if row["provider"] is not None and row["provider"] != run.model.split("/", 1)[0]:
                raise ReceiptError("Harbor trial provider differs from requested route")
            record["trial"] = row
            record["status"] = "completed_with_cost_estimate" if row["agent_reported_cost_usd"] is not None else "completed_cost_unavailable"
    except (ReceiptError, OSError, UnicodeError, ValueError) as exc:
        record["status"] = "execution_incomplete"
        record["error"] = str(exc)
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return record
