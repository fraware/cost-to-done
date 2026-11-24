# Terminal-Bench 4.1: external aggregate cost analysis

This separate analysis derives reported inference cost per successful trial from
public Terminal-Bench submission metadata. It does not execute a model, generate
new benchmark results, or claim independent verification of source trials.

## Source and coverage

[Upstream snapshot](https://github.com/harbor-framework/terminal-bench/tree/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions).
Every committed submission JSON at that exact revision is scanned; records with
the explicit leaderboard identifier `4-1-0` are included. Other versions are
excluded. Each row retains the original source path, Git blob identity, SHA-256,
configuration, source job IDs and aggregate fields. No selective model inclusion
or reordering by price is applied.

For each row, divide the source's `metrics.total_cost_usd` by
`metrics.successes`. Both use the original aggregate record, not the rounded
public leaderboard display. The ratio is unavailable for missing/invalid cost,
zero reported cost, zero successful trials, or inconsistent recorded trial IDs.

## Reproduce

From a trusted Cost to Done checkout with Python 3.11+ and Git:

```bash
git clone https://github.com/harbor-framework/terminal-bench.git upstream
git -C upstream checkout --detach ad4c7aae7b6f1fd80e514dc85768e46d02661bef
python -m scripts.analyze_terminal_bench --upstream-checkout upstream \
  --output terminal-bench-4-1.json
```

The script reads committed blobs from the exact revision. It never imports or
executes upstream task source. The [CI workflow](https://github.com/fraware/cost-to-done/actions/workflows/terminal-bench-snapshot.yml) independently recomputes the aggregate table.

## Interpret carefully

The upstream [metric implementation](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/src/leaderboard/core/metrics.py)
sums trial cost fields and rounds to cents; absent cost fields contribute zero.
Thus the derived ratio is **reported inference dollars per accepted trial**,
not an audited cost-per-completion result. We have not established whether any
trial actually lacks cost, checked original invoices, or reconstructed paired
task-level costs, retry histories and verifier outputs. Infrastructure and
human-review costs are outside this calculation. The upstream success count and
regrading/disqualification policy are inherited, not independently reproduced.

These data describe submitted model-plus-agent configurations. They do not
isolate model effects, establish statistical superiority, or support a
generalized economic ranking. A comparison of exact cost-complete matched
trial receipts is a separate milestone.
