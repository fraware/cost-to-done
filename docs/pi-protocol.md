# Pi model protocol compatibility probe

The pinned Harbor Pi adapter uses `@earendil-works/pi-coding-agent@0.85.1`. Its model client uses OpenAI-compatible Chat Completions streams, including tool declarations and potentially provider-specific request fields. Our gateway's initial HTTP route rejects `stream: true` and unknown request fields. It must not be advertised as compatible with Pi before this mismatch is resolved.

A dedicated GitHub Actions workflow installs the exact Pi version, launches a localhost mock API with a synthetic prompt and fake credential, runs Pi's actual CLI, and logs only **request field names, streaming mode, token cap, and tool count**. No real model or paid provider is contacted. The complete mock request is held in a temporary directory that is removed at the end of the run.

```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent@0.85.1
bash scripts/test_pi_wire.sh
```

The probe establishes what this pinned client sends, without treating the mock assistant's reply as a verified task completion. It also does not establish that Pi is isolated within a Harbor-controlled container. Both the stream parser and financial-accounting policy need independent tests, including stream interruption, missing terminal usage, simultaneous requests, tool-call deltas, retries, and cancellation. No token-price authorization from the existing non-streaming gateway is applied to this wire probe.
