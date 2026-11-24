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

## Pinned snapshot results

The [actual aggregate CI run](https://github.com/fraware/cost-to-done/actions/runs/45402143794)
scanned 75 submission records. Thirty-two have explicit target `4-1-0`, each
with 330 recorded trials and 330 unique trial identifiers. Their combined
reported trial count is 10,560; this count is a sum across submission
records, not an independent proof that all trials are distinct across the cohort.
Thirty-one ratios are defined. One submission records zero successes and retains
its reported $1,011.52 expenditure; its ratio is undefined. The snapshot includes
one submission whose model route is not declared in its source filter. It is
retained and identified by its original source link. The total reported inference
cost across the 32 records is $48,961.61. These records do not
necessarily exhaust the live leaderboard, which can display regraded legacy
rows under different source conventions.

[Download the derived JSON snapshot](data/terminal-bench-4-1.json) ·
[View the public analysis](https://fraware.github.io/cost-to-done/terminal-bench.html)

| Source model route | Agent | Effort | Accepted / recorded | Reported inference cost | Reported cost / accepted trial |
| --- | --- | --- | ---: | ---: | ---: |
| [Route not declared](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-deepseek-v4-1-flash-1017-max-claude-code-regrade.json) | claude-code | max | 127/330 | $184.89 | $1.46 |
| [anthropic/claude-fable-5-2](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-10-anthropic-claude-fable-5-2-max-claude-code.json) | claude-code | max | 217/330 | $16,492.76 | $76.00 |
| [anthropic/claude-haiku-5-5](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-haiku-5-5-max-claude-code-regrade.json) | claude-code | max | 132/330 | $952.47 | $7.22 |
| [fusion](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-14-4-1-0-fusion-none-copilot-cli.json) | copilot-cli | Not declared | 235/330 | $1,987.33 | $8.46 |
| [gemini/gemini-3.1-pro-preview](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-15-4-1-0-gemini-3-1-pro-regrade.json) | antigravity-cli | high | 9/330 | $3,651.15 | $405.68 |
| [gemini/gemini-4-argon](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-13-4-1-0-gemini-4-argon-high-antigravity-cli-regrade.json) | antigravity-cli | high | 183/330 | $1,108.98 | $6.06 |
| [gemini/gemini-4-carbon](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-14-4-1-0-gemini-gemini-4-carbon-high-antigravity-cli.json) | antigravity-cli | high | 213/330 | $1,358.25 | $6.38 |
| [gemini/gemini-4-hydrogen](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-13-4-1-0-gemini-gemini-4-hydrogen-high-antigravity-cli.json) | antigravity-cli | high | 186/330 | $784.24 | $4.22 |
| [gemini/gemini-4-neon](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-20-4-1-0-gemini-gemini-4-neon-xhigh-antigravity-cli.json) | antigravity-cli | xhigh | 202/330 | $1,922.24 | $9.52 |
| [meta/muse-ember-1.0](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-10-meta-muse-ember-1-0-xhigh-muse-code.json) | muse-code | xhigh | 101/330 | $157.18 | $1.56 |
| [meta/muse-wonder-1.0](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-13-4-1-0-muse-wonder-xhigh-muse-code-regrade.json) | muse-code | xhigh | 155/330 | $2,452.31 | $15.82 |
| [moonshotai/kimi-k3.1-pro](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-kimi-k3-1-pro-max-claude-code-regrade.json) | claude-code | max | 197/330 | $1,086.66 | $5.52 |
| [openai/gpt-5.4-mini](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-gpt-5-4-mini-xhigh-codex-regrade.json) | codex | xhigh | 6/330 | $671.57 | $111.93 |
| [openai/gpt-6.1-terra](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-gpt-6-1-terra-max-codex-regrade.json) | codex | max | 176/330 | $874.44 | $4.97 |
| [openai/gpt-6.2-astra](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-17-4-1-0-gpt-6-2-astra-max-codex.json) | codex | max | 205/330 | $1,409.14 | $6.87 |
| [openai/gpt-6.2-sol](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-17-4-1-0-gpt-6-2-sol-max-codex.json) | codex | max | 203/330 | $349.16 | $1.72 |
| [openai/inkling-small-1102-rc17](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-11-4-1-0-inkling-2-small-xhigh-mini-swe-agent.json) | mini-swe-agent | xhigh | 43/330 | $963.65 | $22.41 |
| [openrouter/deepseek/deepseek-v4-pro-0813](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-deepseek-v4-pro-0813-max-claude-code-regrade.json) | claude-code | max | 22/330 | $727.02 | $33.05 |
| [openrouter/fireworks/ember-1](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-15-4-1-0-ember-1-regrade.json) | mini-swe-agent | Not declared | 72/330 | $4,718.49 | $65.53 |
| [openrouter/minimax/minimax-m3](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-minimax-m3-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 25/330 | $1,149.33 | $45.97 |
| [openrouter/mistralai/mistral-large-4-0](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-mistral-large-4-max-claude-code-regrade.json) | claude-code | max | 91/330 | $718.40 | $7.89 |
| [openrouter/moonshotai/kimi-k3](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-kimi-k3-max-claude-code-regrade.json) | claude-code | max | 76/330 | $1,919.83 | $25.26 |
| [openrouter/nvidia/nemotron-3.5-super-vl](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-nemotron-3-5-super-vl-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 1/330 | $167.29 | $167.29 |
| [openrouter/reflection/beam-1.0-501b-a23b](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-beam-1-0-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 21/330 | $220.96 | $10.52 |
| [openrouter/tencent/hy4](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-hy4-max-claude-code-regrade.json) | claude-code | max | 125/330 | $347.60 | $2.78 |
| [openrouter/tencent/hy4-flash](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-19-4-1-0-openrouter-tencent-hy4-flash-none-mini-swe-agent.json) | mini-swe-agent | Not declared | 39/330 | $15.47 | $0.40 |
| [openrouter/tencent/hy4-preview](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-15-4-1-0-hy4-preview-regrade.json) | claude-code | max | 63/330 | $658.09 | $10.45 |
| [openrouter/thinkingmachines/inkling](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-inkling-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 0/330 | $1,011.52 | Undefined |
| [openrouter/thinkingmachines/inkling-small](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-inkling-small-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 3/330 | $49.55 | $16.52 |
| [openrouter/xiaomi/mimo-v2.6-flash](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-mimo-v2-6-flash-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 53/330 | $194.60 | $3.67 |
| [openrouter/xiaomi/mimo-v2.6-pro](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-mimo-v2-6-pro-none-mini-swe-agent-regrade.json) | mini-swe-agent | Not declared | 89/330 | $282.32 | $3.17 |
| [z-ai/glm-5.3-flash](https://github.com/harbor-framework/terminal-bench/blob/ad4c7aae7b6f1fd80e514dc85768e46d02661bef/leaderboard/submissions/2026-11-12-4-1-0-glm-5-3-flash-max-claude-code-regrade.json) | claude-code | max | 122/330 | $374.72 | $3.07 |
