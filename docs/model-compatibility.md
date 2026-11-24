# Model compatibility at the costed tool-calling boundary

**Verified on 2026-11-23:** GPT-6.1 Terra and GPT-6.2 Sol both expose Chat
Completions for text requests, while OpenAI requires the **Responses API**
for tool calling. The first live Harbor/Pi runs (GitHub Actions 45307609892)
attempted those models through a Chat Completions function-tool interface and
produced eight uncertain gateway requests with provider HTTP 400 responses.
The isolated diagnostic (45308445075) identified the rejected parameter as
`reasoning_effort` for both models.

The current gateway and the Pi adapter are explicitly configured for
`openai-completions`, not `openai-responses`. A known Responses-only function
tool model is now rejected in the CLI's zero-spend planning step, and requests
using function tools on those routes are rejected **before ledger admission**.
This avoids treating unsupported API configurations as poor model quality.

GPT-5.4 and GPT-5.4 mini allow Chat Completions function tools only when
`reasoning_effort=none` according to current provider documentation.
The gateway pins this setting for those models when function tools are
present, and Pi is configured with `reasoning_effort=off`. This is an
explicit compatibility choice, not a quality- or capability-equivalent
comparison against the GPT-6 Responses configuration.

**Next interface milestone:** add a native Responses route with independent
request validation, ledger admission, tool-call item exchange, usage accounting,
and mock/real-provider conformance. The present Chat Completions gateway
continues to support deterministic mock models and the GPT-5.4 compatibility
trials. No public comparison across incompatible interfaces is justified.

Sources:
- https://developers.openai.com/api/docs/guides/deployment-checklist
- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/docs/models/gpt-5.4
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
