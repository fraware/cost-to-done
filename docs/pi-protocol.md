# Pi model protocol compatibility probe

The pinned Harbor Pi adapter uses `@earendil-works/pi-coding-agent@0.85.1`. Its model client uses OpenAI-compatible Chat Completions streams, including tool declarations and potentially provider-specific request fields. A live probe of the pinned Pi runtime in [GitHub Actions](https://github.com/fraware/cost-to-done/actions/runs/44743701840) observed `max_completion_tokens`, `messages`, `model`, `store`, `stream`, `stream_options`, and `tools`, with streaming enabled, a 256-token limit, and four tool declarations. The gateway now has a constrained stream parser and accounting contract, subject to its own mock-only compatibility test.

A dedicated GitHub Actions workflow installs the exact Pi version, launches a localhost mock API with a synthetic prompt and fake credential, runs Pi's actual CLI, and logs only **request field names, streaming mode, token cap, and tool count**. The same workflow now executes a second Pi session through the actual gateway handler with a mock-only SSE provider response, confirming its settlement in the local ledger. No real model or paid provider is contacted. The complete mock request is held in a temporary directory that is removed at the end of the run.

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.85.1
bash scripts/test_pi_wire.sh
```

The probe establishes what this pinned client sends and whether the mocked gateway accepts and accounts for it, without treating the mock assistant's reply as a verified task completion. It also does not establish that Pi is isolated within a Harbor-controlled container. The stream parser and financial-accounting policy have dedicated local unit tests for truncation, missing terminal usage, mismatched models, content types and token caps. Multi-turn tool-call deltas, actual Harbor networking, provider retries and cancellation still need independent end-to-end tests. No token-price authorization from the existing non-streaming gateway is applied to this wire probe.
