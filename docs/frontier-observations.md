# First native Responses frontier observations

24 November 2026 UTC. The paid workflow on commit
`d8859b7314a7661e0f0b11b08006ebf834932f24` completed successfully.
Both configurations used the same qualified allocation-repair task, Harbor
0.27.0, Pi 0.85.1, native Responses, low reasoning effort, five maximum
model turns and a 4096-token output cap.

| Model | Harbor verifier | Gateway requests | Settled local estimate |
| --- | --- | ---: | ---: |
| gpt-6.1-terra | pass | 2 | $0.004906 |
| gpt-6.2-sol | pass | 4 | $0.019918 |

Source: [workflow 45315089001](https://github.com/fraware/cost-to-done/actions/runs/45315089001),
[Terra job](https://github.com/fraware/cost-to-done/actions/runs/45315089001/job/138180819195)
and [Sol job](https://github.com/fraware/cost-to-done/actions/runs/45315089001/job/138180819214).
These numbers were transcribed from the completed paid job logs. The original
redacted attestations were archived by the workflow; their GitHub-reported ZIP
artifact identities are recorded below. The ZIP bytes have not been audited
in this repository yet.

| Model | Artifact ID | GitHub-reported ZIP SHA-256 |
| --- | ---: | --- |
| Terra | 14884359711 | 8119b94a0ed4ca0ea00da91a85742bad9a1434d0165fe5df4f54494ad3b7e3f4 |
| Sol | 14885640391 | d2145c2c089a8864fa68d7d65da3902581ecc32b13dad1c34233edac5440e40b |

The source workflow used a separate reasoning-enabled mock gate. Real runs
reported settled local rate-card estimates, not invoice amounts. Independent
verifier replay, actual billed costs and generalization beyond this public
development task remain unverified. Do not interpret this table as a ranking
or evidence of a general economic reversal.
