# First real OpenAI coding-agent observations

**Recorded 24 November 2026 (UTC).** Two independent Harbor 0.27.0 / Pi 0.85.1 trials ran the same qualified allocation-repair task with real OpenAI inference. Harbor reported a verifier pass for both. **These are single-task observations, not model rankings or provider invoices.**

| Exact model snapshot | Harbor verifier | Gateway requests | Elapsed time | Rate-card estimate |
| --- | --- | ---: | ---: | ---: |
| `gpt-5.4-2026-03-05` | Pass | 3 | 61.682371 seconds | $0.021935 |
| `gpt-5.4-mini-2026-03-17` | Pass | 5 | 68.739646 seconds | $0.010698 |

Both trials share task checksum `440c8d60d992606488e02f420e9fc93bafda8b215dc2aaec6dde76ed46183b35`. Each local ledger reported zero pending and uncertain requests, with no budget breach.

## Provenance and limits

Source: [GitHub Actions run 45309990728](https://github.com/fraware/cost-to-done/actions/runs/45309990728), trusted commit `f06e3709a51f0221ccaf2e07cc846ab8d9a52e79`. See the [evidence manifest](../evidence/2026-11-24-first-openai-harbor/manifest.json) for hashes of the redacted source attestations, provider price-schedule identities, and GitHub Actions artifact IDs. The full agent transcripts and OpenAI credentials were intentionally excluded from public artifacts.

The validated hashes demonstrate consistency with archived files, **not independently authenticated executions**. Dollar amounts are settled local gateway rate-card estimates, **not independently reconciled provider invoices**. The Harbor verifier was not separately replayed. With just one task per model there is no defensible general superiority claim.

## Reproduce the integrity check

From the repository root run `python scripts/check_real_smoke_evidence.py`. The validator checks source file hashes, identical task identities, rate-card schedule digests, recorded outcome and ledger closure, and the explicit limitations. It outputs an **unranked** record.

Earlier GPT-6.1 Terra and GPT-6.2 Sol attempts used an incompatible Chat Completions tool interface and do not count as model-quality evidence. See [model compatibility](model-compatibility.md).

## Cost basis clarification

The historical local meter prices all reported input tokens at the declared undiscounted input rate and reported output tokens at the declared output rate. It does not apply cache discounts, cache-write charges, long-context or service-tier adjustments, or invoice reconciliation. These estimates are not guaranteed upper bounds. Original observations and price schedules are unchanged.
