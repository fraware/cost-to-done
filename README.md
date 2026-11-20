# Cost to Done

**Price the result. Not the token.**

> The cheapest AI model might be the most expensive way to finish your work.

[Website prototype](docs/index.html) · [Sample report](docs/report.html) · [Cost calculator](docs/calculator.html) · [Methodology](docs/methodology.md) · [Long-term vision](docs/vision.md)

AI model pricing describes what inference costs. Developers care what **finished work** costs. An inexpensive model that spends multiple attempts failing tests, retransmitting context, or calling tools can cost more per accepted task than an expensive model that finishes the work.

**Cost to Done aims to become the open standard for measuring the real economics of completed AI work.** The eventual product is one command to evaluate competing model and agent configurations on **your own repository, your own tasks, your own verification criteria, and your own budget**, backed by inspectable evidence. Repository repair is the first workload, not the limit of the vision.

## Current status

| Component | Status |
| --- | --- |
| Trial receipt validation and complete retry accounting | Working |
| Cost per verified completion, strict comparable-task checks | Working |
| Task-cluster bootstrap uncertainty intervals | Working, exploratory |
| Offline HTML evidence report and standalone calculator | Working |
| Harbor trial receipt importer | Experimental, tested on offline Harbor-shaped fixtures |
| Real coding-agent execution from this CLI | **Not integrated** |
| Audited public model results | **Not yet available** |

**No real-model performance measurements have been published.** The bundled report demonstrates the design with fictional configurations and synthetic data. It does not describe real providers.

## Quick start

Python 3.11 or newer; no credentials or cloud services needed to reproduce the example.

```bash
git clone https://github.com/fraware/cost-to-done.git
cd cost-to-done
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python examples/generate_synthetic.py
cost-to-done validate examples/synthetic-trials.jsonl
cost-to-done report examples/synthetic-trials.jsonl --demo --output report.html
python -m unittest discover -s tests -v
```

Open report.html locally. For a self-contained product walkthrough, open docs/index.html and docs/calculator.html in your browser. The calculator uses explicitly hypothetical assumptions, not measured model prices or capabilities.

To report a set of trial receipts from a separate trusted executor, run:

```bash
cost-to-done validate path/to/receipts.jsonl
cost-to-done report path/to/receipts.jsonl --output report.html
```

The current validator checks receipt format and consistency. It **does not independently establish** that model calls were billed or that a verifier actually ran. Real-result publication needs executor-linked artifacts and separate corroboration.

## Import Harbor trial results

Cost to Done integrates with [Harbor](https://github.com/harbor-framework/harbor) as a downstream analysis tool rather than attempting to replace its sandboxed execution framework.

```bash
cost-to-done import-harbor path/to/manifest.json --output harbor-trials.jsonl
cost-to-done validate harbor-trials.jsonl
cost-to-done report harbor-trials.jsonl --output harbor-report.html
```

The importer verifies pinned identifiers and checks that job outputs include model identity, task checksum, verifier result, timestamps, and attributable agent cost. Missing or malformed fields are errors, not free attempts. The imported costs are marked **rate-card estimates**, never automatically called actual billed amounts.

See [Harbor import contract](docs/harbor.md). The importer has been unit-tested on offline fixtures based on Harbor's documented trial-result structure, not yet validated on an actual completed Harbor job in this environment.

## Our metric

For a fixed task panel, verification policy and evaluation configuration:

```text
Cost per verified completion =
    all charges for all evaluated trials
    -------------------------------------
       number of verified successes
```

Every paid failure counts, including retries preceding a pass. Zero passes means the metric is undefined, not zero. We publish success rate, total cost, and median duration alongside the ratio.

For comparisons, the current system checks matched task IDs, task/verifier digests, trial counts, and monetary cost basis. It withholds ranking for mismatches. It never attributes a combined **model + harness + retry-policy** effect to model choice alone.

Five or more tasks unlock descriptive 95% task-cluster bootstrap intervals. Those are exploratory and do not establish statistical superiority or generalization to novel tasks. See [Methodology and limitations](docs/methodology.md).

## Example receipt

A line in the JSONL input represents a complete task trial, containing one or more charged attempts. The trial stops on its first verified pass.

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
    {"cost_usd": "0.120", "seconds": 18, "outcome": "fail", "cost_source": "billed"},
    {"cost_usd": "0.080", "seconds": 12, "outcome": "pass", "cost_source": "billed"}
  ]
}
```

The digests are **declared identifiers** until checked against independently archived artifacts. They do not prove a trusted verifier ran. Actual charges and usage-priced estimates must never be mixed into a single monetary ranking.

## The roadmap

1. **Evidence foundation — implemented.** Receipt schema, strict accounting, comparable-task checks, local reports, and calculator.
2. **Verified execution — next.** Pinned Harbor task runs, independently controlled acceptance tests, task selection, verifier artifacts, raw usage and price-versioned evidence.
3. **Bring your own repository — planned.** Evaluate a few realistic fixes against your own test suite within a strict per-configuration spending budget, with actionable recommendations.
4. **Open cost benchmark — long-term.** Publicly auditable task suites, independent reproduction, model/harness cost frontiers, and uncertainty-aware comparisons.
5. **Workload economics — long-term.** Engineering, research and operational tasks; adaptive agent routing; full lifecycle costs including tools and human review.

**The goal is to make the economics of reliable AI work independently measurable, not to create another opaque AI leaderboard.** Our launch strategy prioritizes a consequential experiment around a timely model release, followed by a first-run experience useful enough that developers return to evaluate their own work. See [Vision](docs/vision.md).

## Security, privacy and contributions

The present reporting core does not execute untrusted code, transmit private repository content, or contact external analytics services. Agent execution will need strict separation of the model's workspace from secrets and hidden acceptance tests. Consult [Security](SECURITY.md) before contributing any execution adapter.

Contributions are welcome for independent task qualification, credible verifier designs, privacy-preserving sandboxing, cost accounting, regression tests, and new adapters. See [Contributing](CONTRIBUTING.md).

**License:** MIT.
