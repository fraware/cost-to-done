# Security

This repository validates and renders local receipt data, includes an opt-in Harbor runner, and includes an experimental local inference-admission gateway. Treat JSONL receipts, Harbor results, manifests, and HTTP requests as untrusted inputs. The gateway does not provide independently verified agent network isolation or an absolute billing ceiling.

Do not run future real-agent evaluations in the same execution environment that holds repository secrets, long-lived production credentials, or private acceptance tests. Always scope provider keys and outbound network access. The executable verifier and acceptance tests must be inaccessible for agent modification or inspection during task execution.

Report a security issue privately through a GitHub security advisory if the repository supports private vulnerability reporting. Otherwise, contact the maintainer directly through the GitHub profile. Do not publish executable exploits, keys, or private logs in public issues.

## Experimental inference gateway

The standalone gateway binds to IPv4 loopback and authenticates with a gateway-specific
session token. The separate, containerized live gateway listens on an internal
Docker network and publishes no host port. Keep `OPENAI_API_KEY` exclusively
in the trusted gateway process; never expose it to an evaluated agent.
The supported Chat Completions surface includes bounded, text/function-tool
requests with either JSON replies or **fully buffered** streaming replies.
Streaming must terminate with reported usage before its reservation is settled;
this gateway does not forward streaming chunks incrementally. Unsupported models,
modalities, routes and request fields are rejected. Direct provider egress from
an evaluated agent must be blocked and independently checked. A price authorization
based on a heuristic token estimate is **not a hard provider invoice limit**.
See [docs/gateway.md](docs/gateway.md).

## Operator-only real-provider gateway

`run-harbor-gateway` is experimental. It copies the fixed, qualified task into a private run directory and attaches the upstream credential only to a gateway container through a Compose secret mount. The agent receives a short-lived gateway token, not the provider key. Do not mount a Docker socket, use arbitrary task Compose overrides, publish the gateway port, or upload raw logs without reviewing sensitive content. Rate-card preauthorization is not a hard provider spending limit. A dedicated provider-side financial control and independent invoice reconciliation are prerequisites for monetary claims. See [private trial procedure](docs/live-gateway.md).

## Verified live-runner scope

The CI-only [live rehearsal](docs/live-rehearsal.md) uses Harbor 0.27.0 and a fictional upstream endpoint. Its credential loader, private evidence directory and gateway run as the invoking host UID/GID, avoiding world-writable accounting files. The Docker test is an observed configuration, not an unrestricted sandbox guarantee. Use dedicated low-privilege provider credentials and an independently **enforced** provider spend limit for any commercial trial; monitor and reconcile actual charges after execution. Treat raw Harbor logs and gateway tokens as sensitive until the run terminates and artifacts are reviewed.
