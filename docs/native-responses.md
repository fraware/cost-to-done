# Native Responses metering: restricted prototype

The opt-in Gateway(route="/v1/responses") selects a fixed native OpenAI
endpoint and separate request/usage validation. The default Chat Completions
route is unchanged. This buffered HTTP implementation has passed a Pi/Harbor mock rehearsal;
this is not evidence of GPT-6 model performance.

The request subset supports stateless text messages, local JSON function
declarations, function-call and function-output items, and replay of encrypted
reasoning items. It forces store=false and requests reasoning.encrypted_content.
Hosted tools, multimodal content, provider-side conversation IDs, background
execution are excluded. HTTP streaming is fully buffered. Use a fresh ledger for each experiment.
The admission envelope is a heuristic, particularly for opaque encrypted
reasoning items; it is not a guaranteed tokenizer bound or invoice cap.

Terminal completed/incomplete JSON responses and typed SSE terminal events
with exact model identity and
consistent input/output/total usage settle the estimated cost. Ambiguous
outcomes retain the reservation. Completion status is not task success.
Usage is priced at the existing undiscounted rate card, not actual billing.

Offline tests exercise the request contract, continuation, HTTP dispatch,
accounting and rejection cases. No credentials or paid calls are used.
The non-reasoning Pi wire and credential-isolated Harbor mock gates passed.
Subsequent reasoning-enabled mock and bounded paid tests completed; see [frontier observations](frontier-observations.md), [matched panel](development-panel-observations.md) and [separate replay](real-candidate-replay-observations.md).

Provider references:
- https://developers.openai.com/api/reference/resources/responses/methods/create
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/reasoning

## Buffered HTTP streaming

The SSE parser accepts named or data-only typed events with contiguous sequence
numbers, one response.created identity, and exactly one final completed or
incomplete event carrying consistent usage. It rejects failed, unknown,
duplicated, truncated or reordered events and retains unresolved reservations.
The entire stream is forwarded byte-for-byte after ledger settlement; this
intentionally increases time to first byte. No incremental token delivery is
promised. The parser does not validate the full output semantics. Supported
provider event types are intentionally narrow and need real-provider conformance.

Reference: https://developers.openai.com/api/reference/resources/responses/streaming-events

## Pinned Pi wire observations

The direct local-mock probe passed twice on 04f43af (runs 45313040270 and
45313024025). Pi 0.85.1 sends prompt_cache_key alongside stateless input,
stream=true, store=false, max_output_tokens and function declarations. The
second request contains function_call and function_call_output items. The
metered route drops the client cache-routing key and defaults omitted tool
strictness to false to preserve optional fields in Pi schemas. All input tokens
continue to be priced at the undiscounted rate. Native reasoning and actual Harbor isolation were qualified separately in subsequent controlled rehearsals. LiveConfig selects the matching Harbor API format and gateway endpoint explicitly; the public CLI exposes `--api responses` for qualified bundled tasks.

## Isolated native rehearsal gate

The existing mock-only Harbor workflow now runs both chat and native Responses
configurations with the same qualified task, independent verifier, network
bypass probes and fictional price schedule. Native mode uses the actual
credential loader and ledger with a separate local scripted provider. It must
settle exactly two provider calls ($0.0236 fictional), pass the independent
verifier, and demonstrate the previously tested network checks. Reasoning is
explicitly off for this protocol fixture; a thinking-enabled native replay and
real-model paid trials require their own evidence. CI status is the source of
truth for qualification; committing these fixtures does not establish success.

## Confirmed non-reasoning execution and frontier pilot

The exact-head workflow 45313450820 passed both Chat and Responses jobs on
a71cff1, each with two fictional calls, $0.0236 estimated settlement, verified
repair and all four network probes. PR 29 merged as b01a6f9.

The new frontier workflow adds a low-effort Responses rehearsal. Its scripted
provider returns a synthetic encrypted reasoning item and rejects the next
request unless that same item is returned with the matched function output.
This establishes protocol replay only, not real encrypted reasoning validity.
The paid job is restricted to trusted main, depends on the same workflow's
successful mock gate, and runs one trial each of GPT-6.1 Terra and GPT-6.2 Sol.
Each uses the same task, low effort, five turns, 4096 output token cap and USD 1
estimated admission allowance. No provider hard cap is verified. The completed paid pilot and its limitations are documented in [frontier observations](frontier-observations.md).
