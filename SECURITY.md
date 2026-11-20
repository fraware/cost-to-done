# Security

This repository validates and renders local receipt data, includes an opt-in Harbor runner, and includes an experimental local inference-admission gateway. Treat JSONL receipts, Harbor results, manifests, and HTTP requests as untrusted inputs. The gateway does not provide independently verified agent network isolation or an absolute billing ceiling.

Do not run future real-agent evaluations in the same execution environment that holds repository secrets, long-lived production credentials, or private acceptance tests. Always scope provider keys and outbound network access. The executable verifier and acceptance tests must be inaccessible for agent modification or inspection during task execution.

Report a security issue privately through a GitHub security advisory if the repository supports private vulnerability reporting. Otherwise, contact the maintainer directly through the GitHub profile. Do not publish executable exploits, keys, or private logs in public issues.

## Experimental inference gateway

The gateway binds to IPv4 loopback and authenticates with a gateway-specific
session token. Keep `OPENAI_API_KEY` exclusively in the trusted gateway process;
never expose it to an evaluated agent. Do not use the gateway with untrusted
agent containers until their direct provider egress has been blocked and
independently tested. The API only supports text/function-tool non-streaming
Chat Completions and an exact model name. Requests outside this envelope are
rejected, not forwarded. A price authorization based on a token estimate is
**not a hard provider invoice limit**. See [docs/gateway.md](docs/gateway.md).
