# Rehearse the credential-isolated runner

The [live-runner rehearsal workflow](../.github/workflows/live-rehearsal.yml) executes the actual `execute_live` implementation with Harbor **0.27.0**, Pi **0.85.1**, the production gateway credential loader, SQLite reservations, and the allocation-repair verifier. It uses **no commercial model and no payable credentials**.

The test adds an explicit **CI-only** Compose overlay. That overlay mounts a provider-side fake service on a separate Docker network, replaces only the gateway's production HTTPS transport with an HTTP transport to that mock, and runs direct-network bypass probes inside the actual Harbor task container. The repository's user-facing `run-harbor-gateway` command and production Compose file are unchanged.

The fake provider sends a scripted tool call that edits `/app/allocate.py`, followed by a completed model response. The acceptance checker expects a verifier pass, two mock requests, fully settled fictional cost of **$0.0236**, and blocked provider-DNS, raw-IP and public-IP access. It also rejects billing claims and missing evidence.

The test key is a fixed, published string stored temporarily outside the checkout with mode 0600. The script refuses a different key or execution outside explicitly marked CI. Harbor logs may contain task context or temporary gateway tokens; inspect the archived test evidence before redistribution.

The original Harbor 0.26.0 mock fixtures remain valid historical controls. The live runner pins Harbor **0.27.0** because its Pi adapter supports the per-request `max_output_tokens` setting; 0.26.0 rejects that option. Protocol and task controls must be requalified under 0.27.0 for a matched empirical comparison.

**Evidence boundary:** A passing rehearsal establishes the tested container wiring and bookkeeping with an artificial provider. It does **not** verify the real HTTPS model route, model success rates, provider invoices, or a hard financial ceiling. A real, opt-in, provider-capped run and independent billing audit remain outstanding.
