# First matched native development panel

24 November 2026 UTC. Eighteen paid model trials ran in the predeclared
serial order at commit `343046ab49a722c4d702231352deaa83e1212762`.
Two native OpenAI Responses configurations (low reasoning effort), three
public development tasks, three repetitions per configuration/task pair.
Harbor 0.27.0; Pi 0.85.1; five maximum turns; 4096 output-token cap;
900-second wall-time limit. Every trial received its own estimated admission
allowance and gateway ledger.

| Configuration | Harbor passes | Settled local estimate, total | Estimate per completion |
| --- | ---: | ---: | ---: |
| gpt-6.1-terra | 9/9 | $0.045686 | $0.005076 |
| gpt-6.2-sol | 9/9 | $0.177268 | $0.019696 |

All 18 scheduled trials completed; no missing or unresolved records were
reported. Total known rate-card estimate: $0.222954. Sol's aggregate
estimate per completion was 3.88 times Terra's on these fixtures.

| Task (3 repetitions per configuration) | Terra total | Sol total |
| --- | ---: | ---: |
| Allocation repair | $0.015292 | $0.059306 |
| Dependency ordering repair | $0.016276 | $0.061024 |
| Interval union repair | $0.014118 | $0.056938 |

Source: [completed workflow](https://github.com/fraware/cost-to-done/actions/runs/45317198614),
[paid job](https://github.com/fraware/cost-to-done/actions/runs/45317198614/job/138187607746),
[original artifact](https://github.com/fraware/cost-to-done/actions/runs/45317198614/artifacts/14887210683).
The [18 individual log observations](../evidence/2026-11-24-development-panel/log-observations.json)
are transcribed from the completed job. Their exact decimal sums were
recomputed and matched the printed summary. The archive audit workflow
checks the original ZIP, historical plan, per-trial attestations and summary;
the [completed audit](https://github.com/fraware/cost-to-done/actions/runs/45320390734) verified the original ZIP SHA-256, reproduced the historical plan, matched all 18 log observations, and recomputed the archived summary.

Frozen plan SHA-256:
`d14f761a4a2858d1cee40b7c7ca84d4de026408e486cebca3e3738c91a072e56`.

GitHub-reported original ZIP SHA-256:
`18373500dc766d16d8995ec3ed17b4c6fa14878459140c8d70393fd2aa442614`.

These are rate-card estimates, not invoices. Harbor reported all verifier
passes; actual generated candidates from this cohort were not archived for
independent re-execution. The tasks and reference solutions are public,
and there are only three distinct tasks. No held-out generalization,
statistical model ranking, or reversal of token-price ordering is established.
The measured costs exclude human labor, infrastructure and provider invoice
adjustments.
