# Harbor Pi network-isolation experiment

This is a mock-provider security regression test. It is not a real-model benchmark, financial audit, or comprehensive security certification.

## Objective

Demonstrate that the **actual Harbor task container** can reach the Cost to Done gateway while direct connections to the model provider and a public IP are blocked, including attempts using provider DNS and its raw IPv4 address. Execute a pinned Pi client through the gateway, preserve its Harbor verifier verdict, and reconcile the fictional metering ledger.

## Reproduction

The workflow [Harbor Pi isolated mock evaluation](../.github/workflows/harbor-pi-isolated.yml) uses Harbor 0.26.0, Pi 0.85.1, Docker Compose, and the same allocation-repair source fixture used in the earlier mock trial. Run it using `workflow_dispatch` or push changes to the isolated fixture.

The isolated Compose fixture at [`tests/harbor/compose-isolated.yaml`](../tests/harbor/compose-isolated.yaml) assigns explicit networks.

- `main` (the real Harbor agent and verifier service) is attached exclusively to `ctd_agent_net`, a Docker `internal: true` network.
- `ctd_mock_provider` is attached exclusively to `ctd_provider_net`.
- `ctd_mock_gateway` bridges both networks and holds the fictional upstream credential. The agent receives only the gateway token.
- No service publishes ports on the host. Network isolation follows the container's explicit Docker network membership, independently of Harbor's dynamic egress-control sidecar.

At startup, **before Pi executes**, the task's `main` container runs `probe_egress.py`. It checks the ability to connect to the gateway (positive control), tries connecting directly to the provider by service name and raw IP, tries a public IP, and checks that model-provider credentials are absent. A successful bypass terminates the main service and fails the workflow. The provider supplies its current Docker IPv4 address through a test evidence file; the test does not assume a particular subnet.

The inspector checks the startup proof, the completed Harbor trial and failed verifier verdict (the mock intentionally does not repair the program), the actual Pi message and usage, exactly one upstream mock call, and zero pending or uncertain ledger reservations.

## Evidence interpretation

The original Harbor mock fixture joins the agent, gateway, and provider in one network namespace, so it cannot establish network isolation. The isolated fixture tests a different, restrictive topology. Neither should be treated as equivalent to a production Harbor task unless its complete Compose configuration and runtime are independently audited.

The endpoint probes cover the tested addresses, Docker networking, and execution moment. They do not establish the absence of alternate routes, host sockets, Docker daemon access, kernel exploits, unexpected DNS aliases, or privileged workload modifications. The test task is a trusted fixture; arbitrary user-supplied Compose files and unsafe mounts must remain outside the trusted runner.

The price schedule is entirely fictional; the gateway's accounting entry is not an invoice. The current request price envelope is heuristic and insufficient to guarantee a provider-side monetary ceiling. No paid provider call is part of this CI workflow.

**Release gate:** Public model-cost rankings require a genuine model run, reproducible task verification, provider-side spending controls, and verified charging information. Keep the relevant GitHub issues open until those conditions are met.
