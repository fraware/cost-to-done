# Cost to Done

**The cheapest AI model might be the most expensive way to finish your work.**

Compare the cost of completing the same coding tasks with different AI agent configurations. Import existing Harbor results or structured trial receipts, retain expenditure on failed attempts, and generate a local HTML report. Missing costs stay unavailable.

[Try the browser calculator](https://fraware.github.io/cost-to-done/calculator.html) · [View a synthetic sample report](https://fraware.github.io/cost-to-done/report.html) · [Explore Terminal-Bench evidence](https://fraware.github.io/cost-to-done/terminal-bench.html) · [Documentation](docs/README.md)

## Quick start

Install the [v0.1.0 alpha release](https://github.com/fraware/cost-to-done/releases/tag/v0.1.0). Python 3.11–3.13 on Linux is covered by CI. No API key, Docker or paid service is needed for this example. The package is not on PyPI.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install https://github.com/fraware/cost-to-done/releases/download/v0.1.0/cost_to_done-0.1.0-py3-none-any.whl
cost-to-done demo --output demo.html
```

Open `demo.html` locally in your browser. The report uses synthetic receipts, not model observations; it needs no network to render. Choose a fresh output filename for each run. Windows PowerShell activation is `.\.venv\Scripts\Activate.ps1`; Windows filesystem behavior is not covered by CI. [Installation, source checkout and checksum verification](docs/getting-started.md).

Already have Harbor results? Compare them immediately, with no new inference:

```bash
cost-to-done compare-harbor \
  fast=./jobs/fast careful=./jobs/careful \
  --output comparison.html
```

Replace the example paths with your own completed jobs. The comparison checks matching task identifiers and checksums and shows verifier outcomes, elapsed time and available agent-reported cost estimates. Missing costs stay unavailable. See [matched Harbor comparison](docs/compare-harbor.md).

## External benchmark analysis

[Terminal-Bench 4.1: reported inference cost per accepted trial](https://fraware.github.io/cost-to-done/terminal-bench.html). Recomputed from all 32 explicitly targeted 4.1 submission records at a pinned upstream commit, covering 10,560 recorded trials. GPT-6.2 Sol/Codex and GPT-6.2 Astra/Codex recorded 203/330 and 205/330 accepted trials, respectively, with reported inference expenditure per accepted trial of $1.72 and $6.87. The ratios use third-party reported aggregates with unverified cost coverage and retry history; they are not our own executions, invoices, or a model ranking. See [source and method](docs/terminal-bench-4-1.md).

[DeepSWE recovery accounting](https://fraware.github.io/cost-to-done/deepswe.html). Reconstructed 339 assignment records across 113 shared task names from a pinned publisher export. Reason reports 165 final passes and $1,203.289086 total model spend; recovery spend is included. Codex expenditure is unavailable. No comparative cost ratio or paired task-digest verification. [Source and audit](docs/deepswe-recovery-audit.md).

## Our development experiments

### 18 paid trials, three public repair tasks

| OpenAI configuration | Harbor-reported passes | Total estimated inference cost | Estimated cost / completion |
| --- | ---: | ---: | ---: |
| GPT-6.1 Terra, low | 9/9 | $0.045686 | $0.005076 |
| GPT-6.2 Sol, low | 9/9 | $0.177268 | $0.019696 |

All 18 planned trials passed the Harbor verifier. Estimated cost per completion differed by 3.88× on these three public repair tasks. The [original archive audit](https://github.com/fraware/cost-to-done/actions/runs/45320390734) verified the archived results and reconstructed the prospective plan and accounting. [Full experiment and limitations](docs/development-panel-observations.md).

### A separate pair with fresh offline verifier replay

| OpenAI configuration | Original verifier | Offline replay | Estimated inference cost |
| --- | --- | --- | ---: |
| GPT-6.1 Terra, low | Fail | Fail | $0.003234 |
| GPT-6.2 Sol, low | Pass | Pass | $0.019944 |

Both original verdicts agreed with a fresh verifier process. Terra's expenditure is retained even though the cost-per-completion ratio is undefined. [Evidence and replay details](docs/real-candidate-replay-observations.md) · [Original archive audit](https://github.com/fraware/cost-to-done/actions/runs/45334799801).

These are separate cohorts. Costs are local estimates pricing all reported input tokens at the declared undiscounted input rate and output tokens at the declared output rate. Cache discounts, cache-write charges, other pricing adjustments, infrastructure, and human labor are excluded. The estimates are not reconciled invoices or guaranteed upper bounds. The panel does not establish a general model ranking, a price-order reversal, or performance on unseen repositories.

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

**Current boundary:** the external-task gateway and matched comparison have passed actual Harbor/Pi integration tests with a fictional provider. A fixed public synthetic pilot and a separately guarded four-task upstream development panel are available from source through explicitly authorized maintainer workflows. The upstream panel passed credential-free preflight and starter/reference capture-and-replay qualification; no paid results are claimed. These newer upstream audit workflows are available in the source checkout, not the v0.1.0 wheel. See [upstream controls and evidence review](docs/external-corpus-controls.md). Arbitrary paid repository execution is not enabled.

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

A native trial receipt binds a task identifier, configuration, task digest, verifier digest, harness digest, retry policy and recorded attempts. Imported Harbor results do not establish all of these fields or complete expenditure independently. A configuration includes the model, agent and settings. Distinct configurations must not be interpreted as isolated model effects.

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

Try the released reporting tool on your own evaluation results and [report your experience](https://github.com/fraware/cost-to-done/issues/46). Repository maintainers interested in providing previously unpublished repair tasks should [express interest without posting private source or tests](https://github.com/fraware/cost-to-done/issues/54). Contributions are welcome: reproducible tasks, importer adapters, accounting corrections and evidence audits. Run `python -m unittest discover -s tests -v` before submitting. See [CONTRIBUTING.md](CONTRIBUTING.md) and [Vision](docs/vision.md).

MIT license.
