# Security policy

Cost to Done includes offline parsers and reports, a local metering gateway, and experimental containerized execution. These components have different trust boundaries. No production sandbox or verified provider billing ceiling is claimed.

## Report a vulnerability

Use the repository's [Security page](https://github.com/fraware/cost-to-done/security) to report privately if private vulnerability reporting is enabled. Otherwise contact the maintainer through their GitHub profile. Avoid public exploit details, keys, proprietary source or raw logs.

## Offline tools

Treat JSONL receipts, manifests and Harbor results as untrusted input. Offline reporting does not execute evaluated source. Reports are self-contained; private output files refuse overwrite. A valid receipt establishes consistency, not authentic provenance or billing.

## Experimental gateway

The standalone gateway binds IPv4 loopback; the containerized gateway publishes no host port. Keep the upstream provider credential exclusively in the trusted gateway. Agents receive separate session tokens. Supported constrained Chat Completions and native Responses paths use validated terminal usage for accounting. See [gateway](docs/gateway.md) and [native Responses](docs/native-responses.md).

The gateway reserves estimated cost before forwarding requests. This is not an absolute provider invoice limit. Use independently enforced provider-side financial controls, scoped credentials and invoice reconciliation for paid experiments. Incomplete or uncertain liability must not be treated as zero.

## Execution trust boundary

The experimental live runner uses a trusted checkout, pinned bundled tasks, and a private credential file outside the repository and job outputs. The provider key is mounted into the gateway service. An evaluated agent has only the gateway token and the internal network.

The tested mock topology blocks the direct egress paths exercised by the CI probes. It is not a general container-escape or network-isolation guarantee. Do not mount a Docker socket, add arbitrary Compose overrides, expose gateway ports, or run unreviewed source/tests in a privileged environment.

External repository packaging does not execute source. The CI-only external rehearsal uses a fictional provider; a separately authorized paid pilot accepts only the fixed public synthetic starter. Arbitrary paid external repository execution is disabled.

Independent candidate replay executes fresh pristine acceptance tests in an offline non-root container. Candidate and verifier share Python process state; adversarial verifier integrity is not established. No claim is made that historical generated sources are externally replayable from redacted records alone.

See [live runner](docs/live-gateway.md), [network isolation](docs/network-isolation.md), [repository task scope](docs/repository-task.md), and [candidate replay](docs/candidate-replay.md).

## Sensitive artifacts

Keep raw prompts, generated sources, Harbor logs, private receipt files, SQLite ledgers and credentials private unless explicitly reviewed for publication. Use dedicated low-privilege credentials for authorized trials and rotate credentials if exposure is suspected.
