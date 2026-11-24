# Cost to Done

**The cheapest AI model might be the most expensive way to finish your work.**

Measure the cost of a completed task, including every unsuccessful attempt. Compare agent configurations against the same acceptance criteria and inspect the evidence behind each result.

[v0.1.0 release](https://github.com/fraware/cost-to-done/releases/tag/v0.1.0) · [Project website](https://fraware.github.io/cost-to-done/) · [Interactive calculator](https://fraware.github.io/cost-to-done/calculator.html) · [Documentation](docs/README.md) · [Methodology](docs/methodology.md) · [Repository tasks](docs/repository-task.md)

## Quick start

Python 3.11+ for the local reporting tools. No API key, Docker or paid service needed for this example.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install https://github.com/fraware/cost-to-done/releases/download/v0.1.0/cost_to_done-0.1.0-py3-none-any.whl
cost-to-done demo --output demo.html
```

On Windows, activate the environment with `.venv\Scripts\activate`. [Source installation, distribution checksums and troubleshooting](docs/getting-started.md). Open `demo.html` in your browser. The demo uses synthetic receipts and illustrates failure-inclusive accounting. The report is self-contained and private by default. Choose a fresh output filename for each run.

Already have Harbor results? Compare them immediately, with no new inference:

```bash
cost-to-done compare-harbor \
  fast=./jobs/fast careful=./jobs/careful \
  --output comparison.html
```

The comparison checks matching task checksums and shows verifier outcomes, elapsed time and available agent-reported cost estimates. Missing costs stay unavailable. See [matched Harbor comparison](docs/compare-harbor.md).

## What real experiments have shown

### 18 paid trials, three public repair tasks

| OpenAI configuration | Verified completions | Total estimated inference cost | Estimated cost / completion |
| --- | ---: | ---: | ---: |
| GPT-6.1 Terra, low | 9/9 | $0.045686 | $0.005076 |
| GPT-6.2 Sol, low | 9/9 | $0.177268 | $0.019696 |

Both configurations completed every planned trial. Estimated cost per completion differed by 3.88× in this public development panel. The [original archive audit](https://github.com/fraware/cost-to-done/actions/runs/45320390734) verified the archived results and reconstructed the prospective plan and accounting. [Full experiment and limitations](docs/development-panel-observations.md).

### A separate pair with fresh offline verifier replay

| OpenAI configuration | Original verifier | Offline replay | Estimated inference cost |
| --- | --- | --- | ---: |
| GPT-6.1 Terra, low | Fail | Fail | $0.003234 |
| GPT-6.2 Sol, low | Pass | Pass | $0.019944 |

Both original verdicts agreed with a fresh verifier process. Terra's expenditure is retained even though the cost-per-completion ratio is undefined. [Evidence and replay details](docs/real-candidate-replay-observations.md) · [Original archive audit](https://github.com/fraware/cost-to-done/actions/runs/45334799801).

These are separate cohorts. Costs are local usage-based rate-card estimates, not reconciled invoices. The panel does not establish a general model ranking, a price-order reversal, or performance on unseen repositories.

## Bring your own repository task

Package explicit committed Python source files and standard-library unittest acceptance tests from a trusted local Git repository.

```bash
cost-to-done prepare-repo-task \
  --repository ./my-repo --revision HEAD --name repair-addition \
  --source app/calc.py --test acceptance/test_calc.py \
  --instruction repair.md --output ./repair-task

cost-to-done validate-repo-task ./repair-task
```

The prepared task pins Git objects, staged file hashes and a Python runtime image. Preparation does not execute source code, install dependencies or contact a provider.

Run no-model controls on the defective starter and known correct reference using Harbor 0.27.0, Python 3.12 and Docker. Bind the resulting acceptance evidence with `qualify-repo-task`. Follow the [complete repository-task walkthrough](docs/repository-task.md).

**Current boundary:** the external-task gateway and matched comparison have passed actual Harbor/Pi integration tests with a fictional provider. A fixed public synthetic real-provider pilot is available through an explicitly authorized maintainer workflow. Arbitrary paid repository execution is not enabled.

## Choose the workflow you need

| Goal | Command | Provider access |
| --- | --- | --- |
| Explore the concept | `demo` | None |
| Read one existing Harbor job | `report-harbor` | None |
| Compare existing Harbor jobs | `compare-harbor` | None |
| Validate and analyze your trial receipts | `validate`, `report` | None |
| Reconstruct the public panel report | `report-panel` | None |
| Package and qualify committed Python tasks | `prepare-repo-task`, `validate-repo-task`, `qualify-repo-task` | None |
| Reconstruct a matched fictional comparison | `report-repo-rehearsal` | None |
| Plan a bundled real-provider experiment | `run-harbor-gateway` | None until explicit execution |

Read the [credential-isolated live runner guide](docs/live-gateway.md) before executing a paid bundled trial. That path uses Harbor 0.27.0, Pi 0.85.1, a private provider-key file, a dated price schedule and an estimated admission allowance. The legacy `run-harbor` interface permits direct credential exposure to the agent and is not the recommended execution path.

## The accounting contract

For a fixed task distribution and retry policy:

**Cost per completion = total expenditure across all completed trials ÷ number of verified successful trials.**

Failed attempts and failed trials count toward expenditure. If no trial succeeds, the ratio is undefined. Missing or uncertain financial observations are never imputed as zero. In the planned-panel and repository-comparison protocols, unresolved support withholds comparative ratios.

A trial receipt binds a task identifier, configuration, task digest, verifier digest, harness digest, retry policy and all charged attempts. A configuration includes the model, agent and settings. Distinct configurations must not be interpreted as isolated model effects.

See [methodology](docs/methodology.md), [receipt reconciliation](docs/ledger-reconciliation.md), and the [comparative protocol](docs/comparative-protocol.md).

## Analyze your own receipts

```bash
cost-to-done validate ./trials.jsonl
cost-to-done report ./trials.jsonl --output report.html
```

Each JSONL record describes a trial, potentially containing multiple charged attempts. From a source checkout, generate example receipts with `python examples/generate_synthetic.py`; see the [methodology](docs/methodology.md) for the receipt format. Billed charges and rate-card estimates are distinct cost sources. Receipt consistency does not authenticate execution or billing. Reports are offline, escape dynamic values, and refuse to overwrite existing destinations.

## Evidence and implementation

| Topic | Documentation |
| --- | --- |
| First commercial-model pilot | [GPT-5.4 and GPT-5.4 mini](docs/first-real-observations.md) |
| Native Responses pilot | [Frontier observations](docs/frontier-observations.md) |
| Public matched panel | [18-trial experiment](docs/development-panel-observations.md) |
| Real candidate replay | [Separate cohort](docs/real-candidate-replay-observations.md), [replay contract](docs/candidate-replay.md) |
| Harbor adapter | [Import contract](docs/harbor.md), [direct reports](docs/direct-harbor-report.md) |
| Runtime and metering | [Gateway](docs/gateway.md), [live gateway](docs/live-gateway.md), [native mock rehearsal](docs/live-rehearsal.md) |
| Integration controls | [First experiment](docs/first-experiment.md), [mock Harbor](docs/harbor-mock.md), [isolated Harbor](docs/harbor-isolated.md), [network isolation](docs/network-isolation.md) |
| Repository workflow | [Preparation, qualification and rehearsal](docs/repository-task.md) |

## Security and scope

Use only reviewed source and tests on a trusted host. The tested container topology isolates upstream provider credentials from the agent and blocks the direct-network paths exercised by the mock probes. This is not a production sandbox guarantee. The gateway estimates request admission; a separate provider-side enforced limit and invoice reconciliation are necessary for a verified billing claim. Independent process replay does not establish adversarial verifier integrity.

Report vulnerabilities via [SECURITY.md](SECURITY.md). Keep private source, prompts, traces and credentials out of public artifacts.

## Where this is going

The goal is a one-command evaluation of competing agent configurations on a developer's own work, with complete expenditure accounting and executable acceptance evidence. The current implementation provides local receipt analysis, qualified bundled execution, archived real-provider observations and external repository preparation. General-purpose external execution, independent third-party replication, and a held-out evaluation corpus are outstanding.

Contributions are welcome: reproducible tasks, importer adapters, accounting corrections and evidence audits. Run `python -m unittest discover -s tests -v` before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md) and [Vision](docs/vision.md).

MIT license.
