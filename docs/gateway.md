# Inference admission gateway — experimental

**Status (November 20, 2026): mocked HTTP and container tests; no paid calls have been completed through this gateway.**

The first release exposes a *narrow* OpenAI Chat Completions HTTP endpoint, with fully buffered streaming support. The objective is to ensure that each supported request has an atomic ledger reservation **before** being forwarded, while preserving indeterminate liabilities on failures. It does **not** establish an absolute provider spending cap.

## Supported protocol

- Endpoint: `POST /v1/chat/completions` on IPv4 loopback (`127.0.0.1`). Only the fixed upstream `https://api.openai.com/v1/chat/completions` is used in production. Redirects, arbitrary upstream URLs, client-supplied authorization headers and unrelated API endpoints are excluded.
- One precisely named model, text-only messages, ordinary function tools, and explicit `max_completion_tokens` (1–4096 in the default gateway). A mock-only test configuration opts in to a higher cap, up to 65,536, with the entire upper envelope reserved before forwarding. Streaming is accepted only with `stream_options: {"include_usage": true}` and a validated final usage event. The gateway buffers the full upstream stream before returning it to the client, which changes latency behavior. No image, audio, file, video, search, batch or embeddings paths; unsupported request fields fail closed.
- Client authentication via `Authorization: Bearer $COST_TO_DONE_GATEWAY_TOKEN`, separate from the upstream provider credential. Never supply the upstream key to the agent. A client-supplied `X-Cost-To-Done-Request-Id` is optional and must be unique; retries with an existing ID are rejected.
- Pricing: an operator-supplied JSON schedule containing the exact model name, calendar effective date, HTTPS source URL, and uncached input/output USD per million tokens. The canonical SHA-256 digest identifies the declaration. **The declared rates are not verified by the software.** Confirm them against official provider pricing before any experiment.
- Preauthorization: estimated input tokens = `4 × UTF-8 request bytes + 32 × message count + 64`, plus the requested completion-token cap. This deliberately conservative heuristic is **not a proven tokenizer upper bound**. It does not account for provider-defined extra charges and cannot certify a true maximum invoice.
- Settlement: on a successful JSON response or completed SSE stream with terminal prompt/completion usage, estimate cost from reported tokens at the declared **uncached** rate. Reasoning tokens are assumed included in the provider's completion-token count. Missing usage, mismatched model, HTTP errors, transport errors and unexpected token counts leave the full reservation in `uncertain` state until separately reconciled.

## Zero-spend plan

Create a private local schedule; the following prices are **hypothetical placeholders, not current provider rates**.

```json
{
  "model": "your-exact-supported-model-id",
  "effective_date": "2026-11-20",
  "source_url": "https://platform.openai.com/pricing/",
  "input_per_million_usd": "2.00",
  "output_per_million_usd": "10.00"
}
```

```bash
cost-to-done gateway-serve --price-schedule local-price.json \
  --ledger private/ledger.sqlite3 --budget-usd 0.50
```

This prints a plan without contacting a provider or creating a ledger. To start the local server, use a **separate terminal** outside any agent container, with credentials read exclusively from its private environment:

```bash
export OPENAI_API_KEY='***'                      # upstream provider key, gateway only
export COST_TO_DONE_GATEWAY_TOKEN='your-long-random-session-secret'
cost-to-done gateway-serve --price-schedule local-price.json \
  --ledger private/ledger.sqlite3 --budget-usd 0.50 \
  --serve --acknowledge-no-provider-hard-cap
```

```bash
# Read accounting without requesting provider service.
cost-to-done gateway-status private/ledger.sqlite3
```

The resulting ledger's amounts are **estimated expenditures**, not independently confirmed provider charges. The ledger is private local SQLite, and stores request IDs, reserved amounts, estimated settled amounts and states, not transcripts or API keys. A distinct process or administrator must reconcile uncertain reservations against provider records. The reporting engine must not transform these into `billed` receipts.

## Scope of the security claim

The gateway's request admission path and failure accounting have deterministic mock tests. **A separate isolated Harbor mock fixture now tests gateway-only access from its actual task container; see [Harbor isolation](harbor-isolated.md).** A container able to contact the provider directly or read the provider key defeats the gateway. The agent must run with restricted egress, and the gateway must be reachable over an authenticated channel using a short-lived credential. The product's standalone gateway CLI still binds to loopback; the CI mock gateway listens on a container network interface with fictional credentials. That experimental topology does not authorize exposing the production gateway or running arbitrary Harbor task Compose overrides.

The gateway buffers both non-streaming responses and the *entire* SSE stream before forwarding. It does not support incremental live relaying, separate API endpoints, adaptive provider routing, or billed invoice reconciliation. Client-visible timeouts do not prove provider cancellation. HTTP failures consume reservations pending external confirmation. A response with usage beyond its authorized envelope is treated as uncertain, not as a safely free request.

**Not safe for arbitrary untrusted agents or multi-tenant deployment.** A provider-side project spending limit and access controls are strongly recommended, though some provider alert mechanisms are advisory rather than strictly enforced. Do not use this component to promise a hard invoice maximum.

## Acceptance gates for Issue #5

1. Local forward-path mock tests, authentication, duplicate request protection, admission rejection, concurrency and uncertainty retention. **Implemented and tested locally.**
2. Mock-only Docker Compose topology with direct-bypass probes. **Integration test implemented; review its CI result and limitations in [network-isolation.md](network-isolation.md). An isolated Harbor mock fixture has passed CI for its explicitly configured Docker networks.**
3. Pinned Pi mock-only HTTP compatibility test and stream accounting. **Docker network isolation and mock-backed Harbor Pi orchestration have passed CI independently. Isolation beyond the tested Docker configuration, multi-turn tool execution, and real-provider invoice reconciliation remain outstanding.**
4. Provider usage compared with published dated rates, tool fees and eventual billing records. **Outstanding.**
5. Public release of audited trial evidence with independent verification and no secret exposure. **Outstanding.**

No success on the first gate implies any of the later gates have passed.
