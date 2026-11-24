# First real-model Harbor smoke: scope and evidence

## 2026-11-23 protocol correction

The initial GPT-6.1 Terra / GPT-6.2 Sol Chat Completions tool runs did not
establish coding quality or economic results: both accumulated unresolved
requests after HTTP 400 responses on `reasoning_effort`. OpenAI requires
Responses API for their tool calling.

The subsequent dated GPT-5.4 and GPT-5.4-mini protocol checks
[GitHub Actions #45309534216](https://github.com/fraware/cost-to-done/actions/runs/45309534216)
each returned HTTP 200 with complete terminal usage and no uncertain
reservations. Their fully settled rate-card estimates were $0.000615 and
$0.0001845, respectively, for the diagnostic requests. These are **not
software-repair results or provider invoices**.

This workflow now runs the actual Harbor repair on those **exact dated
GPT-5.4 snapshots** using identical task/verifier inputs, the Pi Chat
Completions adapter at `reasoning_effort=off`, and the gateway's outgoing
`reasoning_effort=none` for function tools. The GPT-6 evaluations remain
blocked until native Responses tool support exists. The workflow uploads
only redacted status evidence and does not claim independent cost billing.

## Experimental scope

The repository's dedicated paid-model workflow tests compatible Chat Completions models; a pair of individual smoke trials does **not** establish comparative model performance.
It runs one qualified allocation-repair task against each of two named OpenAI
model routes. Each run is an independent smoke observation. A single task is
insufficient for a general model ranking.

The supported names and operator-declared standard input/output rates were
checked against their provider model pages on 2026-11-23:

| Model | Input USD / 1M | Output USD / 1M |
| --- | ---: | ---: |
| `gpt-5.4-2026-03-05` | 2.50 | 15.00 |
| `gpt-5.4-mini-2026-03-17` | 0.75 | 4.50 |

Sources: https://developers.openai.com/api/docs/models/gpt-5.4
and https://developers.openai.com/api/docs/models/gpt-5.4-mini

**Explicit spend authorization**: this experiment uses the repository-scoped
GitHub Actions `OPENAI_API_KEY` secret and incurs real inference charges.
It is triggered once by the committed workflow on trusted `main`, or through
a deliberate manual workflow dispatch. The operator has authorized real-model
usage in this project.

Each job has a USD 1.00 local admission ledger and five maximum Pi turns;
the Harbor driver has a 900-second timeout. The ledger's amount is a
**heuristic estimated admission allowance**, not an absolute provider invoice
ceiling. Provider-side hard spend-limit configuration is **not verified**.
The repository credential is mounted only into the gateway container via
a private Compose secret. The actual evaluated Pi agent sees an ephemeral
gateway token and an internal-only network.

The workflow uploads only an attestation containing a Harbor-reported verifier
outcome, task/raw-result hashes, gateway request count, estimated expenditure,
and unresolved-liability flags. Raw prompts, the gateway token, container logs,
and secret files are not uploaded. This limits reproducibility: full local
logs, independently rerun verifiers, and provider invoices are still needed
to support a public benchmark result. The observed estimate treats all input
tokens at the declared uncached rate and excludes independently billed services,
special caching/write charges, refunds, and other provider adjustments.

A completed trial with gateway request receipts confirms upstream inference
attempts. A **successful coding tool execution** additionally needs the
agent's tool transcript and an independent verifier pass. The redacted
attestation by itself does not establish these stronger claims, nor a
five-configuration comparison or invoice-level cost reconciliation.

See `docs/live-gateway.md` and `docs/ledger-reconciliation.md` for the
threat model, original recorder limitations, and further audit obligations.
