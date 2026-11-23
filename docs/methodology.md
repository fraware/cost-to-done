# Methodology and trust boundaries

## Units and accounting

One row in the JSONL format represents a complete, recorded trial of one task by one pinned configuration. A trial terminates at its first verified pass or at a predefined failure/budget boundary. Attempts within a trial are distinct from independent repeated trials of the same task. We sum all recorded attempts, including failed attempts and infrastructure errors; only a final `pass` counts as a completed task.

For configuration \(c\), with complete trials \(i\), cost \(C_i\), and verified completion indicator \(S_i\):

\[D_c = \frac{\sum_i C_i}{\sum_i S_i}, \quad \hat p_c = \frac{\sum_i S_i}{N_c}.\]

\(D_c\) is undefined with zero successes. It is a **ratio of sums**, not an average of per-task success-cost ratios. The latter discards failed tasks or weights tasks inconsistently. Report \(\hat p_c\), total spend, and wall-clock time alongside \(D_c\).

## Comparable design

The analyzer needs at least two configurations and checks that each covers identical task IDs, task/verifier digests, and the same number of trial observations per task. It rejects cost-basis mixtures and refuses to rank mismatches. It also withholds rankings when the declared retry policies differ or any configuration has zero verified completions (undefined cost-per-completion ratio), even for otherwise matched task panels. A trial's cost basis is either `billed` or `rate_card_estimate`. Monetary ranking order uses exact decimal arithmetic, and the HTML report preserves each recorded decimal amount instead of rounding small nonzero costs to zero. The bootstrap chart intervals remain approximate descriptive estimates.

Matching the task panel is necessary but insufficient. A defensible experimental comparison also needs pinned harness versions, model revisions/routes, inference settings, tools, environment resources, budgets, retries, verifier integrity, and task sampling rules. An observed configuration effect is not automatically a pure model effect.

## Uncertainty

With at least five distinct tasks, the analyzer draws 2,000 bootstrap resamples of **tasks**, carrying all within-task replicated trials together and using the same sampled task IDs across configurations. It reports 2.5/97.5 percentile bounds for the cost ratio independently per configuration. Sampled zero-success sets have an unbounded upper cost ratio. Intervals are exploratory; five distinct tasks are inadequate for robust generalization or a precise superiority claim. The current implementation has no multiplicity correction or predeclared equivalence margin.

A real public comparison will need a larger and more representative task panel, prespecified handling of missing trials and infrastructure events, paired contrast intervals, and task-source provenance.

## Local artifact publication

The CLI's receipt exporters and standard HTML report now publish private (POSIX mode 0600) UTF-8 artifacts exclusively. Existing outputs and symlinks are rejected, including attempts to use a receipt file as its own HTML destination. A complete payload is first staged in the destination directory and then published by an exclusive hard link, preventing overwrites and preventing partially written final files. Exporting a receipt together with its provenance sidecar is not one atomic filesystem transaction; an unsuccessful publication rolls back links created by the invocation when still owned by it. The destination filesystem must support local hard links.

## Provenance limits

The current receipt schema validates structure and consistency, **not authenticity**. It does not independently prove a verifier ran, validate the underlying artifacts against its digest, or reconcile invoice charges. The Harbor importer reads trial results from disk and requires a user-pinned manifest, but remains downstream of Harbor's execution and telemetry trust boundary.

The next evidence format will bind trial IDs to immutable executor configuration, verifier outputs, raw token usage, price tables, timestamped receipts, and redacted execution logs. Where cryptographic attestations are appropriate, the trusted attestor, its keys, and its execution control will be explicit.

## Exclusions and missing data

A missing cost is an error, never zero. The Harbor importer treats absent verifier output or exceptions as `infrastructure_error`; it does not credit a pass. Incomplete trials should not silently disappear from the economic denominator. A production execution connector must preserve unfinished workloads, external outage events, stop conditions, and actual budget expenditure. Charging subscription plans, self-hosted GPU costs, search tools, verifier compute, and human review under a common dollar metric is future work.

## Synthetic examples

The bundled fixture is generated from artificial setups with known cost and pass patterns. It illustrates the user experience and exercises the accounting system. It establishes no empirical ranking of existing AI models.
