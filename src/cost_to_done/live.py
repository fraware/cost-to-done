"""Opt-in local Harbor trial through a credential-isolated metering gateway.

The gateway retains a provider key through a read-only Compose secret mount.
Harbor receives only a randomly generated gateway token. This arrangement was
modeled on the passing two-network mock fixture; a real provider run still needs
operator verification, independent provider-side financial limits, and invoice
reconciliation before it supports a publishable cost claim.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import ReceiptError
from .gateway import PriceSchedule
from .responses import ROUTE as RESPONSES_ROUTE
from .harbor import inspect_harbor_job
from .ledger import BudgetLedger, _units
from .network_audit import audit_live_compose
from .model_compat import chat_tools_need_no_reasoning, validate_chat_tool_route

HARBOR_VERSION = "0.27.0"
PI_VERSION = "0.85.1"
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,120}\Z")
_JOB = re.compile(r"[a-z][a-z0-9-]{1,60}\Z")
TRUSTED_TASK_MODULES = {
    "allocation-repair": "allocate.py",
    "interval-union-repair": "intervals.py",
    "dependency-order-repair": "dependency_order.py",
}
_ALLOWED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "USER", "TMPDIR",
                "DOCKER_HOST", "DOCKER_CONTEXT", "XDG_RUNTIME_DIR", "VIRTUAL_ENV")


@dataclass(frozen=True)
class LiveConfig:
    """One trusted operator-controlled task, model and budget authorization."""

    repo_root: Path
    task: Path
    jobs_dir: Path
    model: str
    price_schedule: Path
    key_file: Path
    budget_usd: str
    job_name: str = "gateway-smoke-01"
    max_turns: int = 3
    max_wall_seconds: int = 900
    api: str = "chat"
    reasoning_effort: str = "low"
    capture_candidate: bool = False
    repository_task_sha256: str | None = None
    repository_qualification: Path | None = None

    def validated(self, *, check_key: bool = False) -> "LiveConfig":
        """Check immutable inputs without creating anything or reading secrets."""
        root = self.repo_root.resolve(strict=True)
        if not root.is_dir() or self.repo_root.is_symlink():
            raise ReceiptError("repository root must be a regular directory")
        expected = (root / "experiments/live/compose.yaml", root / "experiments/live/base-compose-ci.yaml", root / "experiments/live/Dockerfile.pi",
                    root / "src/cost_to_done/live_gateway.py")
        if any(not x.is_file() or x.is_symlink() for x in expected):
            raise ReceiptError("repository is missing a trusted gateway execution fixture")
        task = self.task.resolve(strict=True)
        if self.task.is_symlink() or not task.is_dir():
            raise ReceiptError("task must be a real directory")
        external = self.repository_task_sha256 is not None or self.repository_qualification is not None
        if external:
            from .repository_qualification import check_qualification
            if self.repository_task_sha256 is None or self.repository_qualification is None:
                raise ReceiptError("external task requires both a pinned digest and qualification receipt")
            if self.capture_candidate:
                raise ReceiptError("external candidate collection is not qualified")
            if task.is_relative_to(root):
                raise ReceiptError("prepared external task must be outside the trusted runner checkout")
            check_qualification(task, self.repository_qualification, self.repository_task_sha256)
            if check_key and (os.environ.get("GITHUB_ACTIONS") != "true"
                              or os.environ.get("CTD_REHEARSAL_ONLY") != "1"
                              or self.model != "test-model-1" or self.api != "responses"):
                raise ReceiptError("external task execution is mock-only; paid execution is disabled")
        else:
            if (task.name not in TRUSTED_TASK_MODULES or task != root / "tasks" / task.name
                    or (root / "tasks").is_symlink()):
                raise ReceiptError("this experimental gateway runner accepts only bundled qualified tasks")
            for path in task.rglob("*"):
                if path.is_symlink() or not path.resolve().is_relative_to(task):
                    raise ReceiptError("task contains a symlink or escaped artifact")
            module = TRUSTED_TASK_MODULES[task.name]
            required = ("instruction.md", "task.toml", "environment/Dockerfile",
                        f"environment/{module}", "tests/test.sh", "tests/test_state.py",
                        "solution/solve.sh")
            if any(not (task / name).is_file() for name in required):
                raise ReceiptError("qualified task fixture is incomplete")
        if not _MODEL.fullmatch(self.model):
            raise ReceiptError("model must be an exact OpenAI model ID")
        if type(self.capture_candidate) is not bool:
            raise ReceiptError("candidate capture must be explicitly boolean")
        if self.api not in ("chat", "responses"):
            raise ReceiptError("unsupported live API protocol")
        if self.reasoning_effort not in ("off", "minimal", "low", "medium", "high", "xhigh"):
            raise ReceiptError("unsupported reasoning effort")
        if self.api == "chat":
            validate_chat_tool_route(self.model)
        if not _JOB.fullmatch(self.job_name):
            raise ReceiptError("job_name must be lowercase hyphenated text, length 2–61")
        if type(self.max_turns) is not int or not 1 <= self.max_turns <= 10:
            raise ReceiptError("max_turns must be within 1–10")
        if type(self.max_wall_seconds) is not int or not 60 <= self.max_wall_seconds <= 3600:
            raise ReceiptError("max_wall_seconds must be within 60–3600")
        _units(self.budget_usd, allow_zero=False)
        schedule = PriceSchedule.load(self.price_schedule)
        if schedule.model != self.model:
            raise ReceiptError("price schedule and requested model do not match")
        jobs = self.jobs_dir.resolve(strict=False)
        if jobs == root or jobs.is_relative_to(task) or task.is_relative_to(jobs):
            raise ReceiptError("output cannot overlap the repository's trusted task")
        if self.jobs_dir.is_symlink() or (jobs.exists() and not jobs.is_dir()):
            raise ReceiptError("jobs_dir must be a directory, not a symlink")
        target = jobs / self.job_name
        if target.exists() or target.is_symlink() or (jobs / ".sessions" / self.job_name).exists():
            raise ReceiptError("job name already exists; each experiment must have a unique name")
        if check_key:
            key = self.key_file
            if key.is_symlink() or not key.is_file() or key.stat().st_size > 4096:
                raise ReceiptError("provider credential file missing or unsafe")
            if key.stat().st_mode & 0o077:
                raise ReceiptError("provider credential file must not be readable by group or others (chmod 600)")
            resolved = key.resolve(strict=True)
            if resolved.is_relative_to(root) or resolved.is_relative_to(jobs) or resolved.is_relative_to(task):
                raise ReceiptError("provider credential file must be outside repository and run outputs")
            if external and (key.read_bytes().strip() != b"ctd-fake-upstream-key-for-tests-12345678"):
                raise ReceiptError("external rehearsal requires the exact fictional key")
        return LiveConfig(root, task, jobs, self.model, self.price_schedule.resolve(),
                          self.key_file.resolve(strict=check_key), self.budget_usd,
                          self.job_name, self.max_turns, self.max_wall_seconds, self.api, self.reasoning_effort, self.capture_candidate,
                          self.repository_task_sha256, self.repository_qualification.resolve() if external else None)

    def command(self, *, task_copy: Path, token: str) -> list[str]:
        """Prepare shell-free Harbor invocation without any provider credential."""
        native = self.api == "responses"
        return [
            "harbor", "run", "--path", str(task_copy),
            "--agent", "pi", "--model", f"openai/{self.model}",
            "--base-url", "http://ctd_gateway:8866/v1",
            "--api-key-name", "CTD_GATEWAY_TOKEN",
            "--api-format", "openai_responses" if native else "openai_chat_completions",
            "--ak", f"version={PI_VERSION}", "--ak", "skip_install=true",
            "--ak", "model_api=openai-responses" if native else "model_api=openai-completions",
            "--ak", f"max_turns={self.max_turns}",
            *(["--ak", f"reasoning_effort={self.reasoning_effort}"] if native else
              (["--ak", "reasoning_effort=off"] if chat_tools_need_no_reasoning(self.model) else [])),
            "--ak", "max_output_tokens=4096",
            "--agent-env", f"CTD_GATEWAY_TOKEN={token}",
            "--extra-docker-compose", str(self.repo_root / "experiments/live/compose.yaml"),
            "--job-name", self.job_name, "--jobs-dir", str(self.jobs_dir),
            "--n-concurrent", "1", "--n-attempts", "1",
        ] + (["--extra-docker-compose", str(self.repo_root / "tests/live/compose-rehearsal.yaml")]
             if self.repository_task_sha256 is not None else [])


def staged_task_inputs(root: Path, task: Path) -> tuple[tuple[str, ...], bytes]:
    """Resolve the exact staged input names and generated Dockerfile bytes."""
    module = TRUSTED_TASK_MODULES.get(task.name)
    if module is None or task != root / "tasks" / task.name or task.resolve() != task:
        raise ReceiptError("unknown or unsafe trusted task")
    template_path = root / "experiments/live/Dockerfile.pi"
    if template_path.is_symlink() or not template_path.is_file():
        raise ReceiptError("missing trusted Pi Dockerfile template")
    template = template_path.read_text(encoding="utf-8")
    marker = "COPY allocate.py /app/allocate.py"
    if template.count(marker) != 1:
        raise ReceiptError("unexpected trusted Pi Dockerfile template")
    files = ("instruction.md", "task.toml", f"environment/{module}",
             "tests/test.sh", "tests/test_state.py", "solution/solve.sh")
    for name in files:
        source = task / name
        if not source.is_file() or source.is_symlink() or source.resolve() != source:
            raise ReceiptError("missing or unsafe staged task input")
    return files, template.replace(marker, f"COPY {module} /app/{module}").encode("utf-8")


def prepare_task(config: LiveConfig, task_copy: Path) -> None:
    """Stage only the declared fixture files, excluding incidental local artifacts.

    The operator must trust the checkout, including the task and runner template.
    This is not a general untrusted repository execution facility.
    """
    if config.repository_task_sha256 is not None:
        from .repository_qualification import check_qualification
        from .repository_task import validate_repository_task
        check_qualification(config.task, config.repository_qualification, config.repository_task_sha256)
        # Copy the exact declared inputs, validate the staged bytes before changing
        # the Dockerfile, and never include the manifest or incidental files in
        # the image context. The trusted runner supplies the Pi setup.
        manifest = json.loads((config.task / "ctd-task-manifest.json").read_bytes())
        task_copy.mkdir(mode=0o700)
        for name in (*manifest["files"], "ctd-task-manifest.json"):
            dest = task_copy / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(config.task / name, dest)
        copied = validate_repository_task(task_copy)
        if copied["task_input_sha256"] != config.repository_task_sha256:
            raise ReceiptError("staged repository task digest mismatch")
        (task_copy / "ctd-task-manifest.json").unlink()
        template = (config.repo_root / "experiments/live/Dockerfile.pi").read_text(encoding="utf-8")
        marker = "COPY allocate.py /app/allocate.py"
        if template.count(marker) != 1:
            raise ReceiptError("unexpected trusted Pi Dockerfile template")
        (task_copy / "environment/Dockerfile").write_text(template.replace(marker, "COPY workspace/ /app/"), encoding="utf-8")
        return
    files, dockerfile = staged_task_inputs(config.repo_root, config.task)
    task_copy.mkdir(mode=0o700)
    for name in files:
        source = config.task / name
        destination = task_copy / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    (task_copy / "environment/Dockerfile").write_bytes(dockerfile)
    if config.capture_candidate:
        # This changes task identity; historical cohorts keep capture disabled.
        task_toml = task_copy / "task.toml"
        module = TRUSTED_TASK_MODULES[config.task.name]
        with task_toml.open("a", encoding="utf-8") as stream:
            stream.write(f'\n[[artifacts]]\nsource = "/app/{module}"\ndestination = "candidate.py"\n')


def plan_live(config: LiveConfig) -> dict[str, Any]:
    """Produce a zero-spend plan without reading secrets or creating files."""
    c = config.validated()
    return {
        "status": "plan_only", "model": c.model,
        "repository_task_sha256": c.repository_task_sha256,
        "repository_execution_scope": "mock_only" if c.repository_task_sha256 else "bundled",
        "candidate_capture_requested": c.capture_candidate,
        "api": c.api, "reasoning_effort": c.reasoning_effort if c.api == "responses" else None,
        "agent": "pi", "agent_version": PI_VERSION,
        "harbor_version": HARBOR_VERSION, "task": str(c.task),
        "price_schedule_sha256": PriceSchedule.load(c.price_schedule).digest,
        "operator_budget_usd": c.budget_usd,
        "max_turns": c.max_turns, "max_wall_seconds": c.max_wall_seconds,
        "agent_provider_credential": "not_mounted",
        "provider_key_mount": "gateway_container_only",
        "agent_network": "docker_internal_only_in_declared_compose_fixture",
        "provider_hard_cap": False,
        "billing_verified": False,
        "warning": "Admission uses estimated maximum usage. Confirm a separate provider-side spending limit; billing might exceed this ledger.",
    }


def _preflight() -> None:
    """Require the exact pinned Harbor toolchain and a running Docker daemon."""
    try:
        got = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ReceiptError(f"install harbor=={HARBOR_VERSION} in Python 3.12+ first") from exc
    if got != HARBOR_VERSION:
        raise ReceiptError(f"Harbor {got} is installed; expected {HARBOR_VERSION}")
    try:
        p = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                           capture_output=True, text=True, timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReceiptError("Docker daemon is unavailable") from exc
    if p.returncode or p.stdout.strip() != "linux":
        raise ReceiptError("Linux-container Docker daemon is necessary")


def _run_process(command: list[str], *, env: dict[str, str], log_file: Path, timeout: int) -> int:
    """Run once and terminate the process group on timeout, preserving logs."""
    fd = os.open(log_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as log:
        process = subprocess.Popen(command, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            raise ReceiptError(
                "Harbor timed out. Detached containers or provider charges might continue; check them manually."
            ) from exc


def _audit_compose_before_live(root: Path, environment: dict[str, str]) -> dict[str, Any]:
    """Reject unsafe static Compose declarations before any provider call.

    This does not validate Harbor's dynamic network behavior. Errors are
    deliberately redacted since Compose diagnostics might contain session
    tokens or host-local file paths.
    """
    cmd = ["docker", "compose", "-f", str(root / "experiments/live/base-compose-ci.yaml"),
           "-f", str(root / "experiments/live/compose.yaml"), "config", "--format", "json"]
    try:
        proc = subprocess.run(cmd, env=environment, capture_output=True, text=True,
                              timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReceiptError("Docker Compose structural preflight was unavailable") from exc
    if proc.returncode:
        raise ReceiptError("Docker Compose structural preflight failed; no model call was launched")
    try:
        parsed = json.loads(proc.stdout)
    except (ValueError, UnicodeError) as exc:
        raise ReceiptError("Docker Compose did not return valid JSON") from exc
    return audit_live_compose(parsed)


def execute_live(config: LiveConfig, *, acknowledged: bool = False) -> dict[str, Any]:
    """Execute one specifically trusted task through the isolated gateway.

    Neither success nor settlement establishes verified provider billing. The
    operator must independently enforce account limits and reconcile invoices.
    This does not publish reports or automatically delete retained liabilities.
    """
    if not acknowledged:
        raise ReceiptError("live execution needs explicit acknowledgement of external provider spending control")
    c = config.validated(check_key=True)
    if os.name != "posix":
        raise ReceiptError("live execution currently needs a POSIX host")
    _preflight()
    session_dir = c.jobs_dir / ".sessions" / c.job_name
    if session_dir.exists():
        raise ReceiptError("session already exists")
    session_dir.mkdir(parents=True, mode=0o700)
    task_copy = session_dir / "task"
    prepare_task(c, task_copy)
    evidence = session_dir / "evidence"
    evidence.mkdir(mode=0o700)
    gateway_token = secrets.token_urlsafe(48)
    environment = {key: os.environ[key] for key in _ALLOWED_ENV if key in os.environ}
    environment.update({
        "CTD_REPO_ROOT": str(c.repo_root),
        "CTD_EVIDENCE_DIR": str(evidence),
        "CTD_PRICE_FILE": str(c.price_schedule),
        "CTD_PROVIDER_KEY_FILE": str(c.key_file),
        "CTD_BUDGET_USD": c.budget_usd,
        "CTD_GATEWAY_TOKEN": gateway_token,
        "CTD_GATEWAY_ROUTE": RESPONSES_ROUTE if c.api == "responses" else "/v1/chat/completions",
        # Run the gateway as the same non-root owner as the private evidence and
        # chmod-0600 provider secret files mounted from the operator host.
        "CTD_RUN_UID": str(os.getuid()),
        "CTD_RUN_GID": str(os.getgid()),
    })
    if c.repository_task_sha256 is not None:
        # Only the fixed synthetic repository fixture reaches this mock route.
        environment.update(CTD_REHEARSAL_TASK="repository-addition-repair", CTD_REHEARSAL_REASONING="low")
    command = c.command(task_copy=task_copy, token=gateway_token)
    outcome: dict[str, Any] = {
        "schema_version": 1,
        "status": "started", "model": c.model,
        "api": c.api, "reasoning_effort": c.reasoning_effort if c.api == "responses" else None,
        "task_fixture": c.task.name,
        "repository_task_sha256": c.repository_task_sha256,
        "repository_execution_scope": "mock_only" if c.repository_task_sha256 else "bundled",
        "candidate_capture_requested": c.capture_candidate,
        "job_name": c.job_name, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "price_schedule_sha256": PriceSchedule.load(c.price_schedule).digest,
        "operator_budget_usd": c.budget_usd, "provider_invoice_reconciled": False,
        "provider_side_hard_cap_verified": False,
        "agent_network_declared_internal": True,
        "provider_key_declared_gateway_only": True,
    }
    try:
        outcome["topology_preflight"] = _audit_compose_before_live(c.repo_root, environment)
        exit_code = _run_process(command, env=environment,
                                 log_file=session_dir / "harbor.driver.log",
                                 timeout=c.max_wall_seconds)
        outcome["harbor_exit_code"] = exit_code
        if exit_code != 0:
            raise ReceiptError("Harbor returned a nonzero exit status; inspect private driver log")
        info = inspect_harbor_job(c.jobs_dir / c.job_name)
        if info.get("complete") is not True or info.get("observed_trials") != 1:
            raise ReceiptError("Harbor did not complete exactly one trial")
        trial = info["trials"][0]
        if trial["agent"] != "pi" or trial["model"] != c.model or trial["provider"] != "openai":
            raise ReceiptError("Harbor trial identity differs from planned route")
        outcome["trial"] = trial
        ledger_path = evidence / "ledger.sqlite3"
        if not ledger_path.exists():
            raise ReceiptError("gateway ledger was not created; unknown expenditure")
        ledger = BudgetLedger(ledger_path)
        snapshot = ledger.snapshot()
        outcome["gateway_snapshot"] = snapshot.to_dict()
        outcome["gateway_entries"] = ledger.entries()
        if (snapshot.schedule_sha256 != PriceSchedule.load(c.price_schedule).digest
                or snapshot.pending or snapshot.uncertain or snapshot.breached):
            outcome["status"] = "requires_financial_reconciliation"
        elif not ledger.entries():
            outcome["status"] = "no_metered_requests"
        else:
            outcome["status"] = "completed_with_unverified_rate_card_estimate"
    except (ReceiptError, OSError, ValueError, UnicodeError) as exc:
        outcome["status"] = "incomplete_or_uncertain"
        outcome["error"] = str(exc)
        # Preserve any readable ledger even if Harbor fails before inspection.
        # Missing/corrupt ledger does not establish zero expenditure.
        try:
            ledger_path = evidence / "ledger.sqlite3"
            if ledger_path.is_file():
                ledger = BudgetLedger(ledger_path)
                outcome["gateway_snapshot"] = ledger.snapshot().to_dict()
                outcome["gateway_entries"] = ledger.entries()
        except (ReceiptError, OSError, ValueError):
            pass
    result_path = session_dir / "run-summary.json"
    with result_path.open("x", encoding="utf-8") as output:
        json.dump(outcome, output, indent=2, sort_keys=True)
        output.write("\n")
    result_path.chmod(0o600)
    outcome["summary_file"] = str(result_path)
    outcome["private_job_dir"] = str(c.jobs_dir / c.job_name)
    return outcome
