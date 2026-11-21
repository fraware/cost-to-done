# Compare existing Harbor jobs, without running a model

**Status:** Offline, descriptive comparison of recorded Harbor trial files. This command does not execute agents, request API credentials, re-run verifiers, validate provider invoices, or establish model rankings.

## From two Harbor jobs to an inspectable comparison

```bash
python -m pip install -e .

cost-to-done compare-harbor \
  fast=/path/to/first-harbor-job \
  careful=/path/to/second-harbor-job \
  --output comparison.html
```

Open `comparison.html` locally in your browser. The file includes paired task outcomes, observed wall-clock times, available agent-reported cost estimates, and abbreviated SHA-256 digests of the underlying recorded trial results. It has no JavaScript, third-party fonts, CDN dependencies, or telemetry. The command writes the new report as a private file (mode 0600 on POSIX), refuses an existing output, and rejects output paths inside the original Harbor jobs.

Use 2–8 named jobs. A name contains ASCII letters, digits, dots, hyphens or underscores and starts with a letter or digit. Each job must contain exactly one recorded trial for every task and a complete Harbor job summary with the expected number of trials. Repeat experiments are handled separately through the canonical trial-receipt analysis pipeline.

**Task identity is checked strictly.** All jobs must contain exactly the same task identifiers, with an identical Harbor task checksum for each. A mismatch or incomplete job is an error, not an omitted comparison row. Harbor versions that generate different task checksums cannot be treated as equivalent here without separately validating and declaring their task definitions.

## What the numbers mean

- Pass, fail and infrastructure error are *Harbor-recorded* verifier outcomes. They have **not** been independently validated against a trusted verifier. The report shows the infrastructure error category separately.
- Available dollar amounts are **agent-reported estimates** from Harbor, not independently confirmed charges or invoice totals. If even one trial in a job lacks a cost, the job's aggregate cost displays as **Unavailable**, never as a zero-filled sum.
- The task pairing is an input-consistency check, not evidence of unbiased task selection, model independence, randomized run order, or matching software environments. Model/harness and retry policies could differ.
- The command deliberately generates **no ranking or winning configuration**. Formal cost-per-verified-completion comparisons use pinned receipts, audited verifiers, a matched execution design, and billing reconciliation. See [Methodology](methodology.md) and [Ledger reconciliation](ledger-reconciliation.md).

Use `cost-to-done report-harbor JOB --output single.html` for one Harbor job. Use `cost-to-done reconcile-harbor` only when a dedicated settled inference ledger and the full immutable provenance inputs are available.
