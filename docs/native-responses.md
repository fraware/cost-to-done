# Native Responses metering: restricted prototype

The opt-in Gateway(route="/v1/responses") selects a fixed native OpenAI
endpoint and separate request/usage validation. The default Chat Completions
route is unchanged. This is a buffered HTTP prototype, not a Pi/Harbor
integration or evidence of GPT-6 model performance.

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
The next milestone is pinned Pi wire conformance,
credential-isolated Harbor rehearsal, and a separately authorized paid test.

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
