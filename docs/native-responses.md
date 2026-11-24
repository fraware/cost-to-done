# Native Responses metering: restricted prototype

The opt-in Gateway(route="/v1/responses") selects a fixed native OpenAI
endpoint and separate request/usage validation. The default Chat Completions
route is unchanged. This is a non-streaming prototype, not a Pi/Harbor
integration or evidence of GPT-6 model performance.

The request subset supports stateless text messages, local JSON function
declarations, function-call and function-output items, and replay of encrypted
reasoning items. It forces store=false and requests reasoning.encrypted_content.
Hosted tools, multimodal content, provider-side conversation IDs, background
execution and streaming are excluded. Use a fresh ledger for each experiment.
The admission envelope is a heuristic, particularly for opaque encrypted
reasoning items; it is not a guaranteed tokenizer bound or invoice cap.

Terminal completed/incomplete JSON responses with exact model identity and
consistent input/output/total usage settle the estimated cost. Ambiguous
outcomes retain the reservation. Completion status is not task success.
Usage is priced at the existing undiscounted rate card, not actual billing.

Offline tests exercise the request contract, continuation, HTTP dispatch,
accounting and rejection cases. No credentials or paid calls are used.
The next milestone is buffered Responses SSE handling, Pi wire conformance,
credential-isolated Harbor rehearsal, and a separately authorized paid test.

Provider references:
- https://developers.openai.com/api/reference/resources/responses/methods/create
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/reasoning
