# Gateway-to-agent network separation: executable mock test

**Scope.** This is an integration test for a deliberately narrow Docker topology. It does **not** prove that a Harbor-managed agent, a real cloud-provider client, or a production host has the same isolation properties. No paid API requests or real billing occur in this experiment.

The fixture runs three containers on two Docker bridge networks:

- `agent` attaches exclusively to `agent_net`, declared `internal: true`, with no provider credentials.
- `gateway` attaches to both networks and holds only a **fictional** upstream credential. The gateway authenticates agent requests, reserves a conservative usage-price estimate, forwards permitted requests to the mock provider, and records the result in SQLite.
- `provider` attaches exclusively to `provider_net` and only accepts its fictional gateway-held credential. None of the Compose services publishes a host port.

```text
  agent    --->   gateway   --->    provider
  agent_net       both networks     provider_net
    internal      admission ledger  Docker bridge
```

Run on a Linux Docker host with Compose v2:

```bash
bash scripts/test_gateway_network.sh
```

The test fails if the agent establishes a TCP connection to the provider's DNS name, raw Docker-network IP, or a public IP, or if it contains the upstream credential. It also checks an unauthenticated HTTP request, one permitted metered request, duplicate-request rejection, over-budget rejection, exact provider-forward count and final ledger state. All expectations use mock-only data and prices.

The Linux Docker bridge restriction is an infrastructural property of this particular Compose test. It does not establish isolation on different container runtimes, host network modes, custom task Compose overrides, privileged containers, attached Docker sockets, Kubernetes, or environments with altered firewall routing. Docker image tags in this smoke test are not digest-pinned. The test itself cannot establish absence of kernel/runtime vulnerabilities.

## Remaining Harbor prerequisites

Harbor's Pi agent supports `--base-url`, `--api-key-name`, `--api-format openai-chat-completions`, and a custom `model_api=openai-completions` option. Connecting it to a gateway needs a **Harbor-controlled agent network without direct provider egress**, a gateway address reachable within that network, and a proven request-format match.

The current gateway is non-streaming and runs on host loopback in the product CLI. Pi's streaming request behavior has not yet been demonstrated compatible with that gateway. Connecting the agent to a non-loopback gateway without independently validating its network isolation would create an unsafe bypass path. No route through this test is labeled an enforced monetary cap, since price-token envelopes are estimates and final provider charges need independent reconciliation.

The next acceptance test must use the actual Harbor Pi runtime and verify both network isolation and protocol compatibility, with a mock upstream first. Paid-model execution follows only once that end-to-end path is established and separately authorized.
