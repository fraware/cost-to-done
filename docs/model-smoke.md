# Run a real model once — controlled smoke test

**Stage:** Prepared and unit-tested, with **no paid model trial executed yet**. This documents an opt-in local execution workflow. The Harbor/Pi provider path has not been validated end-to-end with an API credential.

The repository includes a real software-repair task with an independent no-op failure and reference-solution pass established by [Harbor controls](first-experiment.md). This command launches a single new model-backed Harbor trial, captures the raw result, and records its locally inspectable evidence.

## 1. Dry-run without Docker, model credentials, or expenditure

```bash
python -m pip install -e .
cost-to-done run-harbor --task tasks/allocation-repair --model openai/YOUR_MODEL_ID
```

The output is a JSON execution plan. It includes the task-content digest, pinned agent version, full shell-free argv, requested network hosts and limits. It performs **no inference**.

## 2. One actual model trial on a trusted machine

Prerequisites are **Linux/macOS**, Python 3.12+, a working Docker daemon, `harbor==0.26.0`, an API key, and a **provider-side account or project spending quota** you have configured and independently verified. The CLI refuses to execute without an explicit acknowledgement. It does **not** establish or enforce a hard dollar spending cap. GitHub Actions does not run these commands by default.

```bash
python -m pip install 'harbor==0.26.0'
# Export OPENAI_API_KEY or ANTHROPIC_API_KEY in your shell securely.
# Configure a hard provider-side monetary spending limit before execution.
cost-to-done run-harbor \
  --task tasks/allocation-repair \
  --model openai/YOUR_MODEL_ID \
  --max-turns 10 \
  --max-wall-seconds 900 \
  --job-name local-trial-001 \
  --execute --acknowledge-no-dollar-cap
```

Supported initial routes are `openai/<model>` and `anthropic/<model>` through the pinned `pi` agent. Avoid recording credentials in arguments, task files, or commits. Agent software runs in a container and obtains credentials for API access; treat agent code and dependencies as privileged with respect to those credentials. Use a dedicated, limited API key, not an organization-wide secret. This task's verifier is project-controlled, not cryptographically isolated from a malicious host.

We pin Harbor 0.26.0, Pi 0.85.1, one Harbor attempt and one concurrent task. Pi's `max_turns` is a cap on completed model turns, **not** a guarantee on API request counts, tool invocations or dollars. The host imposes a best-effort wall-clock timeout and terminates Harbor's process group. Detached containers and in-flight API requests might outlive it. Trial expenses might exceed any estimate. A terminal or network interruption is not evidence that billing stopped.

The task disallows general internet access. The launcher supplies provider-host access during agent execution and a small set of setup hosts (`raw.githubusercontent.com`, `github.com`, `nodejs.org`, `registry.npmjs.org`) needed to install the pinned agent. Harbor's actual network-isolation behavior and any additional bootstrap hosts need a real integration test before we make an isolation claim. No private repository data belongs in this task fixture.

## 3. Inspect the outcome

The command writes private local files under `runs/`, ignored by Git. Review the execution record at `runs/local-trial-001.execution.json` and the driver log at `runs/.local-trial-001.driver.log`. The logs may contain sensitive data; do **not** publish them directly.

```bash
cost-to-done inspect-harbor runs/local-trial-001
```

The execution record includes the task input digest, configured model and agent, result file hash, reported verifier outcome, and either an agent-reported cost estimate or an explicit absence of cost. It does **not** constitute an audited monetary receipt, reproduce an invoice, or establish statistical performance. A missing result or incompatible model identity is a failed smoke test. Run results are never automatically published.

Before any external performance claim, independently recompute task and verifier digests, verify the agent could not read hidden acceptance materials, review raw trajectories and metering, reconcile provider charges or priced usage, and repeat the experiment on a task panel that was fixed before comparing models. One trial cannot support a cost-efficiency ranking.

## Known execution limitations

- Missing provider keys, Harbor installations, Docker, network setup hosts or unsupported model routes halt the run.
- The pinned Pi installation has not been independently tested with the two selected providers in this project.
- Only an externally enforced provider budget protects against runaway spending. A timeout does not provide financial containment.
- The local receipt inspector trusts Harbor's recorded verifier and cost telemetry; independent checks remain necessary.
- `run-harbor` is an explicit research smoke-test interface, not a service for executing arbitrary user-submitted repositories or remotely exposed tasks.
