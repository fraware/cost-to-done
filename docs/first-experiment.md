# First experiment — a genuine execution qualification, not an AI leaderboard

**Status:** Both Docker-backed Harbor controls passed the strict qualification checks on November 20, 2026 in [GitHub Actions run 44725906881](https://github.com/fraware/cost-to-done/actions/runs/44725906881). The pinned task revision earned `reward=0.0` under `nop` and `reward=1.0` under `oracle`; neither trial raised an exception. No paid-model result is available.

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

The workflow uploads raw job artifacts for audit and records the resolved Docker base-image digest. Following the initial run, the Dockerfile was pinned to the observed `python@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0` image digest. Harbor 0.26 stores trial `result.json` directly under each named trial folder, rather than a `trials/` directory. The parser accepts both audited layouts. Transitive Python package versions are not fully lockfile-pinned, a remaining reproducibility limitation.

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

## Initial observed Harbor evidence

The first Docker-backed run, [44724971452](https://github.com/fraware/cost-to-done/actions/runs/44724971452), recorded correct no-op/oracle verdicts, though the workflow's final inspection step failed due to an outdated directory-layout assumption. The verified rerun, [44725906881](https://github.com/fraware/cost-to-done/actions/runs/44725906881), passed all steps. Both rerun trials recorded Harbor task checksum `62884685a34a548962fa6771cb25ded8ab2dc5a486163fb72ca337f40748910e`, reflecting the image-digest pin added after the initial run.

[Recorded trial excerpts](../tests/fixtures/) now preserve the fields from the successful rerun, including identifiers, timestamps, agent names and rewards. Raw artifact SHA-256 digests were `67c72058a95197a24378be19ca8f1ec42464bd47ec43f189fe9ae877a6afb32f` (`nop`) and `6e854b9b0f687c6600b86ba2eb947da332c6a6ad09ca19b0c33643c26459c86d` (`oracle`). The archived full logs and verifier outputs are available through the run's Actions artifact, subject to GitHub's retention period.

Both controls report `cost_usd: null`; they serve exclusively as task controls. This one-task validation supplies no evidence about model quality, cost efficiency, or generalization.
