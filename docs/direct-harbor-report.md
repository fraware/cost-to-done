# One-command Harbor evidence report

Existing Harbor jobs can be inspected without provider credentials, a model run, or a user-authored manifest:

```bash
cost-to-done report-harbor path/to/harbor-job \
  --output harbor-evidence.html \
  --title "My coding-agent experiment"
```

Open `harbor-evidence.html` in a browser. It is a self-contained HTML document: no JavaScript, third-party assets, calls to providers, analytics, or network dependency. The command inspects existing Harbor trial files and creates a new mode-0600 output file outside the job directory. It refuses to overwrite an existing report or modify the original Harbor artifacts.

## Interpretation

The page displays the Harbor job's recorded trial count and declared completeness, pass/fail/infrastructure-error outcomes, full trial-result SHA-256 digests, elapsed time, agent identity, model route, and **agent-reported cost estimates** where available. Incomplete jobs are explicitly labeled. If any trial has missing cost telemetry, the aggregate financial total is marked *Unavailable* instead of silently summing a subset. Existing zero-dollar agent estimates are preserved as zero-dollar **reports**, not evidence of a provider's actual invoice.

This command does **not** run task verification again, validate the contents of historical task files, independently authenticate the provider or executor, or reconcile a provider invoice. Harbor's recorded pass is only a reported outcome. The output deliberately produces no model ranking or cost-per-success comparison: arbitrary tasks, differing agent harnesses, and unverified prices are not comparable just because their results are found in one Harbor job.

The stronger receipt workflow remains [`reconcile-harbor`](ledger-reconciliation.md), which needs a dedicated gateway ledger, pinned task and verifier digests, a priced route, and a reviewed execution contract. Those checks also do not constitute invoice reconciliation.

## Use cases

This report is useful for a first-pass audit of a single Harbor job, sharing a clearly qualified evaluation snapshot, and identifying missing metering or incomplete trials before preparing a rigorous comparison. It is intentionally read-only and needs only the normal `cost-to-done` Python installation.
