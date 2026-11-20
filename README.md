# One Task, Real Cost

**Price a result. Not a token.**

An experimental, zero-dependency reporting core for comparing the full expense of **verified task completions**. This repository is a stage-0 prototype, **not a functioning model benchmark runner**. It validates and summarizes task-trial receipts supplied by a separate, trusted executor. It does not call model APIs, verify patches, grade tests, or run untrusted code.

## Try it locally

Python 3.11+ and no API keys needed.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python examples/generate_synthetic.py
realcost validate examples/synthetic-trials.jsonl
realcost report examples/synthetic-trials.jsonl --output report.html --title 'Synthetic example' --demo
python -m unittest discover -s tests -v
```

Open `report.html` in any browser. Open `calculator.html` for an interactive, fully offline scenario calculator. Its inputs are **hypothetical assumptions**, and its projections are separate from evidence-backed reports. All inputs in the fixture are **synthetic**, use fictional configurations, and establish nothing about real AI models. The resulting HTML has no external resources, JavaScript, analytics, or network requests. Its presentation is optimized for a public-facing receipt, without publishing private prompts or transcripts.

## Data contract

Each line in the input JSONL corresponds to a **completed evaluation trial** under one pinned task and configuration. One trial has one or more charged attempts. The first verified pass terminates the trial. Example:

```json
{
  "trial_id": "run-0001",
  "configuration_id": "model-plus-harness-v1",
  "task_id": "issue-001",
  "task_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "verifier_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "harness_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "retry_policy": "one-feedback-retry",
  "attempts": [
    {"cost_usd": "0.12000", "seconds": 18.0, "outcome": "fail", "cost_source": "billed"},
    {"cost_usd": "0.08000", "seconds": 12.0, "outcome": "pass", "cost_source": "billed"}
  ]
}
```

Digests refer to independently archived task, verifier and harness artifacts. This prototype checks equality of provided digests across comparisons; it **does not** re-hash or inspect any underlying artifacts. A production runner must establish and sign that provenance itself.

The two allowed cost sources are `billed` (provider-recorded charges) and `rate_card_estimate` (priced from observed usage). Do not label subscription usage as provider-billed API cost. Real benchmark receipts need pinned provider routing, tariff date, usage tokens, caching fields, reasoning mode, tool charges, timestamps and a preserved cost-calculation function. This initial format is a minimal contract, not sufficient to audit actual billing.

## Metric and comparison rules

For one configuration, `total cost of every completed trial / number of trials ending in verified pass` is the cost per verified completion. Expenses from failures and earlier retry attempts are included. Zero passes yield an undefined (unbounded) ratio, not $0. The success percentage uses completed trials as its denominator. Median duration uses full-trial wall time, including all retries.

A comparison is ranked only if every configuration covers identical task IDs, identical verifier digests, and identical per-task trial counts, with consistent cost sources. Different harnesses, model settings or retry policies need explicit interpretation as different **configurations**, not isolated effects of model choice. Recorded infrastructure errors are retained in expenditure and disclosed as counts; the current minimal format cannot adjudicate whether an outage is attributable to the model or a provider, and users must audit such incidents independently.

For at least five distinct tasks, the report shows a descriptive 95% percentile interval from 2,000 bootstrap resamples **clustered by task**. Five tasks do not establish reliable generalization; the interval is exploratory and excludes other sources of uncertainty such as benchmark selection, evolving versions, and pricing changes. No interval constitutes a significance test.

For two-configuration comparisons with different task sets or a mix of billed charges and estimates, rankings and intervals are withheld.

## Security and privacy

- Inputs are read locally, and reporting executes no trial code.
- The HTML report escapes user-controlled names and contains no live scripts.
- Running a real agent against a repository entails untrusted-code execution. Future execution integration must use containers with strong network, credential, filesystem and verifier isolation. GitHub Actions on pull requests must never expose evaluation provider keys to untrusted code.
- Receipts cannot prove tests were honestly executed or costs genuinely billed. Such claims depend on an independently auditable runner and raw provider accounting.

## Next milestone

Integrate an existing pinned sandboxed evaluation framework (Harbor is a candidate) rather than inventing a second agent loop. Attach task manifest hashes, verifier results, model settings, raw API usage and price-versioned metering. Benchmark at least five relevant model configurations on matched, verified tasks, then publish redacted raw receipts, the methodology, and the HTML report together. Only these measured runs qualify for a public model leaderboard.

## License

MIT. See `LICENSE`.
