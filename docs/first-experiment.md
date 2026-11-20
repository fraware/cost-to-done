# First experiment — a genuine execution qualification, not an AI leaderboard

**Status: local baseline/reference controls executed; GitHub-hosted Harbor controls pending until a successful Actions run is inspected.** No paid-model result is available.

## Purpose

An agent-cost comparison needs a trustworthy binary acceptance result before any model is priced. The first test task is a Python repair: fix a proportional cent allocation function that rounds independently, mishandles invalid inputs, and loses precision on large integers. The verifier uses only the standard library and an isolated filesystem fixture.

The acceptance contract specifies exact integer arithmetic, conservation of cents, largest fractional remainder assignment, deterministic tie-breaking, and invalid-input behavior. The public verifier exercises these conditions with deterministic tests. This task is an engineering smoke test, **not a representative sample of coding work**.

## Local controls, no credentials or Docker

From the repository root, with Python 3.11 or newer:

```bash
python scripts/qualify_task.py tasks/allocation-repair
python -m unittest discover -s tests -v
```

The script copies the same broken starter into two different temporary directories, runs the tests on one, applies the separately held reference solution to the other, and runs the same tests again. Qualification passes only if the unchanged starter fails and the reference succeeds. It prints SHA-256 hashes of the starter, verifier, and reference script. The task scripts are trusted, project-owned code; this local control is **not** a secure sandbox.

## Independent Harbor container controls

The [Harbor task qualification workflow](../.github/workflows/harbor-controls.yml) pins `harbor==0.26.0`, starts separate Docker-backed `nop` and `oracle` jobs, reads their actual `trials/*/result.json` files and rejects results unless:

- Exactly one trial is present in each job.
- The no-op agent has reward 0 and the oracle agent has reward 1.
- Both controls report exactly the same task name and task checksum.
- The verifier records a valid binary reward without infrastructure exceptions.

The workflow uploads raw job artifacts for audit and records the resolved Docker base-image digest. The image tag remains mutable, and transitive Python package versions are not fully lockfile-pinned. Those limitations must be resolved before scientific or procurement-grade comparisons.

For manual execution on a trusted Docker host with Python 3.12+, run:

```bash
python -m pip install 'harbor==0.26.0'
harbor run --path tasks/allocation-repair --agent nop --job-name controls-nop --jobs-dir control-jobs --n-concurrent 1
harbor run --path tasks/allocation-repair --agent oracle --job-name controls-oracle --jobs-dir control-jobs --n-concurrent 1
python scripts/check_harbor_controls.py --nop control-jobs/controls-nop --oracle control-jobs/controls-oracle
```

## What qualifies as the next, real agent-economics datum

A model-backed evaluation must use the exact same task and verifier, a pinned agent and model configuration, an explicit monetary spending policy enforced outside the agent, a fresh environment, full usage telemetry, raw verifier evidence, and a cost basis clearly identified as invoice-reconciled or usage-priced. Stop immediately at the specified budget; model-generated text cannot override the budget or verifier. A no-op/oracle control never enters the model-cost leaderboard.

We do **not** claim that GitHub's execution environment or this verifier is a formal isolation guarantee. For independent evaluation, the agent must have no access to acceptance tests, reference patch, credentials, or scoring artifacts.
