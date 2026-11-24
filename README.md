# Cost to Done

**Price the result. Not the token.**

> The cheapest AI model might be the most expensive way to finish your work.

[Compare Harbor runs](docs/compare-harbor.md) · [Direct Harbor report](docs/direct-harbor-report.md) · [Explore the static experience](docs/index.html) · [Sample evidence report](docs/report.html) · [Interactive cost calculator](docs/calculator.html) · [Methodology](docs/methodology.md) · [Model smoke test](docs/model-smoke.md) · [Harbor mock integration](docs/harbor-mock.md) · [Isolated Harbor test](docs/harbor-isolated.md) · [Receipt reconciliation](docs/ledger-reconciliation.md) · [Vision](docs/vision.md) · [Private real-provider trial](docs/live-gateway.md) · [OpenAI credential preflight](docs/openai-access.md)

Token prices describe a unit of inference. Developers purchase **completed work**. A model that generates cheap tokens while wasting attempts, hallucinating fixes, or failing tests can incur more expense per successful task than a higher-priced model.

**Cost to Done** is an open-source project to make the *cost of verified AI work* measurable, inspectable, and comparable. The long-term product is a one-command way to benchmark competing agent configurations on **your own work**, backed by a public standard for trial receipts, executable verification, and cost accounting. Our starting point is repository-level engineering tasks. The same evidence contract can eventually support research, data, and operational agents.

## What exists today

| Component | Status | What it does |
| --- | --- | --- |
| Receipt validator | **Working** | Validates per-trial attempts, artifact digests, cost sources, retry accounting, and success termination |
| Cost-per-completion analysis | **Working** | Includes failed attempts, blocks invalid comparisons, and computes task-cluster bootstrap intervals where supported |
| Local HTML reports | **Working** | Generates standalone, offline evidence summaries without trackers or remote scripts |
| Matched Harbor job comparison | **Working (descriptive)** | Compares two to eight complete jobs against identical task checksums; reports observations and agent cost estimates without claiming billed-model rankings |
| Cost calculator | **Working** | Interactive hypothetical scenario analysis, separate from measured performance |
| Harbor receipt importer | **Experimental** | Converts pinned Harbor trial result files into local, **agent-reported price estimates**; refuses missing cost and mismatched identities |
| Mock-backed coding-agent execution | **CI verified** | Harbor 0.26.0 and Pi 0.85.1 now exercise both a single-call failed task and a two-call scripted tool repair accepted by an independent verifier; paid-model execution is still outstanding |
| Mock Harbor agent network isolation | **CI verified for one topology** | The actual Harbor task reaches the gateway while direct provider DNS, provider IP, and public IP probes fail; not a production security guarantee |
| Harbor + gateway receipt reconciliation | **Mock-CI verified** | Joins one completed Harbor trial and a dedicated, fully settled gateway ledger into a canonical JSONL receipt and audit metadata; monetary values remain estimates |
| Credential-isolated live runner | **Mock-rehearsed, not paid-tested** | Harbor 0.27.0 and Pi 0.85.1 execute a scripted repair using the production credential loader, admission ledger and internal Docker network; commercial-provider execution and independent billing remain outstanding |
| Public model leaderboard | **Not yet published** | Awaiting controlled runs and independently checked verification/provenance |

**The [credential-isolated real-provider gateway path](docs/live-gateway.md) is mock-rehearsed.** It accepts only the qualified allocation-repair task and mounts upstream credentials in a dedicated gateway container. Its separate [live-runner rehearsal](docs/live-rehearsal.md) completed a verified two-request scripted repair using a fake provider in [CI run 44926843287](https://github.com/fraware/cost-to-done/actions/runs/44926843287). This is execution-system evidence, not a commercial-model or invoice result.

**There are no real-model benchmark results in this repository yet.** The example report uses generated synthetic data from fictional configurations. It cannot support claims about the performance or cost of actual providers.

**Reproducible integration evidence:** [Harbor Pi mock integration](docs/harbor-mock.md) verifies a single-turn failed task. The [isolated Harbor integration](docs/harbor-isolated.md) now checks two scenarios under the same network policy: a one-call, failed task ($0.0036 simulated expenditure), and a two-call scripted repair with an actual agent tool invocation and passing independent verifier ($0.0236 simulated expenditure). [GitHub Actions run 44828369078](https://github.com/fraware/cost-to-done/actions/runs/44828369078) passed both scenarios. Runtime tests check direct-provider DNS and IP bypass attempts inside Harbor's `main` container. **The repaired code was scripted by a fake provider, and the costs are fictional. No real model or paid provider was contacted.** The same workflow now validates the [canonical receipt export](docs/ledger-reconciliation.md) for both outcomes, retaining the verifier verdict, aggregated charges, raw Harbor result hash, and ledger price-schedule identity.

## Quick start

Python 3.11+; no API credentials or paid services needed for the local prototype.

```bash
git clone https://github.com/fraware/cost-to-done.git
cd cost-to-done
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .

python examples/generate_synthetic.py
cost-to-done validate examples/synthetic-trials.jsonl
cost-to-done report examples/synthetic-trials.jsonl \
  --output report.html --title "Synthetic comparison" --demo
python -m unittest discover -s tests -v
```

Open `report.html` locally. Reports and exported receipt/evidence files are created privately and never overwrite existing destinations; choose a fresh output filename for each run. Or open `docs/index.html`, then use the interactive calculator. The calculator takes **assumptions**, not model measurements.

To analyze real trial receipts supplied by a trusted executor:

```bash
cost-to-done validate path/to/trials.jsonl
cost-to-done report path/to/trials.jsonl --output real-report.html
```

Valid receipts alone **do not** authenticate a verifier execution or establish that charges were genuinely billed. This version accepts declared provenance, checks consistency, and preserves the cost basis. Future releases will strengthen provenance with linked raw evidence and an independently executed verifier.

## Report an existing Harbor job in one command

Already have Harbor trial artifacts? No model credentials, manifest, or new inference run is needed:

```bash
cost-to-done report-harbor path/to/harbor-job --output harbor-evidence.html
```

The resulting offline HTML shows Harbor-reported passes, failures, infrastructure errors, task and result hashes, elapsed time, and cost estimates where available. **It does not rank models, independently validate a historical verifier, or claim invoiced costs.** Missing cost data stays explicitly unavailable. See [Direct Harbor report](docs/direct-harbor-report.md).

## Compare existing Harbor jobs — zero inference

```bash
cost-to-done compare-harbor \
  fast=path/to/first-job \
  careful=path/to/second-job \
  --output harbor-comparison.html
```

This offline report pairs matching task outcomes and available agent-reported price estimates. It refuses missing trials, duplicated task IDs, and mismatched task checksums. It **does not rank models or claim independently verified outcomes or provider invoices**. See [Matched Harbor comparison](docs/compare-harbor.md).

## Import Harbor trials (experimental)

Harbor provides sandboxed agent execution and structured per-trial results. Cost to Done reads those existing outputs rather than reproducing Harbor's agent loop. Import is guarded by a manifest with pinned task checksums, verifier digests, agent identity, and harness identity.

```bash
cost-to-done import-harbor path/to/manifest.json --output harbor-trials.jsonl
cost-to-done validate harbor-trials.jsonl
cost-to-done report harbor-trials.jsonl --output harbor-report.html
```

See [Harbor import contract](docs/harbor.md). The importer is validated against offline fixtures based on Harbor's documented trial-result schema. The separate `inspect-harbor` path has processed real Harbor task-control and mock-Pi trial files in GitHub Actions. It does not run agents, audit hidden test execution, inspect provider invoices, or support a genuine leaderboard claim by itself.

## The central metric

For a pinned task distribution and configured retry policy:

\[
\mathrm{CostToDone} = \frac{\sum_{i=1}^{N}\ \text{all charges in completed trial }i}{\sum_{i=1}^{N}\mathbf{1}[\text{trial }i\text{ verified success}]}
\]

Both the money spent on failed trials **and** the money spent on failed attempts preceding a successful one appear in the numerator. The denominator counts task trials, not successful model messages. If nothing passes, the ratio is undefined; it is never shown as zero dollars.

**Never rank incompatible comparisons.** The current analyzer withholds monetary rankings for mismatched task sets, different per-task repetition counts, or mixed charged/estimated prices. Distinct model+harness combinations are distinct **configurations**; their effects must not be attributed to model quality alone.

Uncertainty estimates are descriptive 95% task-cluster bootstrap percentile intervals with a fixed seed. They are not hypothesis tests or guarantees of performance on unseen repositories. See [Methodology](docs/methodology.md).

## Data contract

Each JSONL line represents one complete task trial; a trial can contain multiple charged attempts under a pinned retry policy.

```json
{
  "trial_id": "example-001",
  "configuration_id": "model+harness+settings",
  "task_id": "issue-001",
  "task_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verifier_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "harness_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "retry_policy": "one-feedback-retry",
  "attempts": [
    {"cost_usd": "0.12000", "seconds": 18, "outcome": "fail", "cost_source": "billed"},
    {"cost_usd": "0.08000", "seconds": 12, "outcome": "pass", "cost_source": "billed"}
  ]
}
```

The hexadecimal digests are **declared identifiers** in this receipt format, not proof that referenced artifacts exist. `billed` and `rate_card_estimate` have deliberately different meanings; subscriber quotas, free inference, tool charges, and self-hosted equipment need their own accounting policy before they can enter a common comparison.

## Long-term roadmap

1. **Evidence foundation.** Local-first receipts, honest cost arithmetic, readable reports, strict comparability. **Implemented.**
2. **Verified execution.** Pinned Harbor-based trials, task qualifications, controlled model/harness configurations, raw usage and verifier-evidence linkage. **Next.**
3. **Bring your own repository.** Small tasks and acceptance tests from a project; isolation, one-command evaluation, spend caps, reruns, and useful recommendations. **Planned.**
4. **Open cost-to-done benchmark.** Audited public tasks, third-party reproductions, evolving model choices, empirical cost frontiers, and uncertainty-aware comparisons. **Vision.**
5. **Workload economics.** Model routing by task class, organizational cost simulations, human-review costs, and completed-work optimization across agents, tools, and environments. **Vision.**

The ambition is an **open, independently reproducible account of AI labor economics**, beginning with a tool useful to an individual software developer. More detail is in [Vision](docs/vision.md).

## Security and reproducibility

- The current validator runs locally without executing task code or contacting external services.
- HTML reports have no third-party scripts, analytics, or remote assets. Dynamic values are escaped.
- Future agent execution must isolate secrets, source, verifier, filesystem, and network access. Public CI never needs provider API credentials.
- Pin task revisions, verifier binaries, agent/harness versions, model routes, inference settings, price dates, and trial order for any real comparison.
- Never publish private prompts, proprietary source, API keys, or model traces without explicit authorization.

See [Security](SECURITY.md) for reporting vulnerabilities.

## Contribute

This is early-stage infrastructure with an intentionally demanding evidence standard. Valuable contributions include independently verifiable repository tasks, new import adapters with pinned source fixtures, accounting corrections, privacy-preserving execution, and reproducibility audits. Read [CONTRIBUTING.md](CONTRIBUTING.md).

**License** · MIT.


## Run the first model-backed smoke test (opt-in)

Use the **credential-isolated** path for new experiments. Harbor 0.27.0, Docker and a dated official price schedule are prerequisites. This command is a **zero-spend plan** until execution is explicitly authorized:

```bash
cost-to-done run-harbor-gateway \
  --model YOUR_EXACT_CHAT_COMPLETIONS_MODEL_ID \
  --price-schedule /absolute/path/to/prices.json \
  --provider-key-file /secure/path/upstream-key \
  --budget-usd 0.25
```

The model key is held by the gateway service instead of the evaluated agent. The displayed budget governs **estimated request admission**, not final billed expenditure. Confirm the provider's separately **enforced** spending limit before opting into real execution. [Live-runner instructions](docs/live-gateway.md) describe the financial and isolation limitations. The prior `run-harbor` interface permits direct provider-key exposure to the agent; it is retained for explicit legacy experiments and is **not the recommended security path**. No commercial-model trial has been completed.

## Docker gateway isolation experiment

A reproducible **mock-only** Docker Compose experiment now tests network separation independently of model providers. A simulated agent lives on an internal-only network, a metering gateway spans that network and a mock-provider network, and a fictitious provider records exactly which requests were forwarded. The agent is tested against direct provider DNS, raw-IP, and public-IP bypasses, as well as authorization and budget rejection.

```bash
bash scripts/test_gateway_network.sh
```

The test uses Docker Compose on Linux and makes **no paid API calls**. Its results apply to the stated Compose topology, not to Harbor or a production deployment. See [Network isolation methodology](docs/network-isolation.md) and the dedicated [GitHub Actions workflow](.github/workflows/gateway-isolation.yml).

## Experimental inference budget gateway

The dedicated [Pi protocol compatibility probe](docs/pi-protocol.md) exercises the pinned coding agent against a mock endpoint and the gateway. Streaming outcomes are buffered until terminal usage has been validated; this is **not** a claim of compatibility with Harbor's container networking or live provider billing.

An opt-in local HTTP gateway now performs conservative pre-admission for one
constrained OpenAI Chat Completions route with buffered streaming and an immutable-identity price
schedule, distinct client/provider credentials, and a persistent SQLite ledger.
Its monetary accounting is **based on declared rate-card estimates**. The
estimated authorization is not a universal tokenization bound or a provider
invoice guarantee. It has not yet been connected to Harbor or used in a paid
model trial. See [Gateway limitations and usage](docs/gateway.md).

```bash
cost-to-done gateway-serve --price-schedule local-price.json \
  --ledger private/ledger.sqlite3 --budget-usd 0.50  # plan only
```

## First real execution qualification

The first software-repair task and its no-op/reference controls are now in [`tasks/allocation-repair/`](tasks/allocation-repair/) and [`docs/first-experiment.md`](docs/first-experiment.md). Reproduce the local qualification without keys or Docker:

```bash
python scripts/qualify_task.py tasks/allocation-repair
```

GitHub Actions separately runs the official Harbor `nop` and `oracle` agents in containers, checks their raw verifier outcomes, and archives the evidence. These are **qualification controls, not model performance or cost measurements**. Read the experimental protocol before interpreting any output.
