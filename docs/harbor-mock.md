# Harbor + Pi + metered gateway integration

This is a **mock-only execution proof**, not a model cost benchmark or a provider billing statement. It exercises a real pinned coding-agent process, Harbor task orchestration, a local budget gateway, a fake model endpoint, and an executable verifier.

## Reproduce in GitHub Actions

Run [Harbor Pi mock integration](../.github/workflows/harbor-pi-mock.yml) using `workflow_dispatch`, or push a change to its declared fixture paths. The workflow uses Harbor 0.26.0 and Pi 0.85.1. It prepares a temporary copy of the allocation-repair task with Pi installed during image construction. The task is a smoke-test derivative, **not the same image/checksum** as the separately qualified no-op/oracle controls.

The gateway and mock provider run as separate Compose services within Harbor's task environment. Mock provider traffic is local; no real provider credentials are supplied. The task's network restrictions remain active during agent execution. The Docker-only bypass tests are documented in [Network isolation](network-isolation.md). A **separate** [isolated Harbor Pi fixture](harbor-isolated.md) now tests direct provider DNS, raw IPv4, and public IPv4 bypasses from Harbor's actual task container. The original shared-namespace fixture is retained as a protocol regression and does not itself establish network isolation.

The workflow checks a completed Harbor trial with the expected failed verifier outcome, a Pi assistant message with successful termination and usage, exactly one fake-provider request, and a SQLite ledger with a settled fictional charge and zero outstanding reservations. The fake model deliberately responds `OK` without repairing the allocator; **verifier reward 0 is the expected, correctly graded outcome**. A mock API response error is rejected by the inspector instead of counting as a successful transport test.

## Evidence and economic interpretation

The fixed mock reports 100 input and 40 output tokens. The fictional schedule uses $20 per million input tokens and $40 per million output tokens, producing a **fictional estimated charge of $0.0036**. The ledger is an internal request-accounting receipt; there was **no billed model expenditure**. CI retains trial records, a provider-call marker, the mock SQLite database, and verifier logs as a short-lived workflow artifact. The task and result must be rechecked independently before use in any empirical comparison.

## Boundaries

- This CI run evaluates one mock request and one task. It is not evidence of real-model success, provider billing, general task quality, or model ranking.
- The gateway reserves spending using a byte-based token envelope and provider-declared usage. Neither quantity is a verified invoice bound.
- This special mock gateway opts in to a completion-token cap up to 65,536 because Harbor 0.26.0's Pi adapter does not expose a direct output-token override. The production default stays at 4,096.
- The task image installs Pi and its dependencies during Docker image construction, while task execution uses Harbor's restricted network. Reproducing the build still depends on package registries; transitive npm package resolution is not hermetically pinned.
- Harbor's separate network controls and the project's Docker-only bypass tests do not establish a comprehensive production trust boundary for provider keys. The gateway still needs isolated deployment and reconciliation with actual provider invoices.

The next release gate is one paid model trial, using an independently capped account or gateway plus verified egress, followed by a matched multi-task panel and a publicly inspectable report. Until then, no public model leaderboard is justified.
