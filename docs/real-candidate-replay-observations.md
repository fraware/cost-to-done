# First real-candidate replay cohort

24 November 2026 UTC. One allocation-repair trial per configuration, with
candidate capture enabled, at source commit
`dbf621c4bec9abd261e9a74b93707211dc0239fd`. This is a separate cohort from
the matched 18-trial development panel; the task checksum changed when the
artifact declaration was enabled.

| Configuration | Harbor outcome | Fresh verifier | Calls | Local estimate | Cost/completion |
| --- | --- | --- | ---: | ---: | ---: |
| gpt-6.1-terra | Fail | Fail | 2 | $0.003234 | Undefined |
| gpt-6.2-sol | Pass | Pass | 4 | $0.019944 | $0.019944 |

Total known expenditure: $0.023178. Both ledgers report no pending or uncertain
requests and no budget breach. The Terra final-source digest matches the
unchanged defective starter. This identifies its final state; it does not
identify why the agent left that state. Sol's final-source digest differs.
Both captured sources were replayed in fresh offline non-root containers
against the same pristine verifier, with cleanup confirmed. The CI jobs
succeeded because they checked agreement, including agreement on failure.

[Source workflow](https://github.com/fraware/cost-to-done/actions/runs/45320220501).
[Terra job](https://github.com/fraware/cost-to-done/actions/runs/45320220501/job/138197656077).
[Sol job](https://github.com/fraware/cost-to-done/actions/runs/45320220501/job/138197656129).
The complete redacted log attestations and original ZIP identities are
preserved in [the evidence directory](../evidence/2026-11-24-real-candidate-replay/).
A [completed zero-inference audit](https://github.com/fraware/cost-to-done/actions/runs/45334799801) compares those records against the original
ZIP archives and the pinned starter and verifier identities.

The financial estimates are not invoices. The independent process replay
occurred during the trusted workflow, and the actual generated source bytes
were not published. External replay of Sol's historical source is therefore
not supported by this redacted evidence. The verifier and candidate share
Python process state; adversarial verifier integrity is not established.
One trial per configuration supports neither a general ranking nor an
estimate of success probability. Do not pool the cohorts after observing
their outcomes.

## Cost basis clarification

The historical local meter prices all reported input tokens at the declared undiscounted input rate and reported output tokens at the declared output rate. It does not apply cache discounts, cache-write charges, long-context or service-tier adjustments, or invoice reconciliation. These estimates are not guaranteed upper bounds. Original observations and price schedules are unchanged.
