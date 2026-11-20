# Gateway-to-agent network separation: executable mock test

**Scope.** This is an integration test for a deliberately narrow Docker topology. It does **not** prove that a Harbor-managed agent, a real cloud-provider client, or a production host has the same isolation properties. No paid API requests or real billing occur in this experiment.

The fixture first runs a simulated agent, a gateway, and a mock provider, then launches a separately metered **actual pinned Pi CLI container** in the same internal-only agent network. Both gateways connect to the mock-provider network. All five services use two Docker bridge networks:

- `agent` and `pi_agent` attach exclusively to `agent_net`, declared `internal: true`, with no provider credentials. The second container installs Pi 0.85.1 at image-build time.
- `gateway` and `pi_gateway` attach to both networks and hold only a **fictional** upstream credential. The gateway authenticates agent requests, reserves a conservative usage-price estimate, forwards permitted requests to the mock provider, and records the result in SQLite.
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

The test fails if either agent establishes a TCP connection to the provider's DNS name, raw Docker-network IP, or a public IP, or if it contains the upstream credential. It also checks an unauthenticated HTTP request, permitted metered requests, duplicate-request rejection, over-budget rejection, exact provider-forward counts and both final ledger states. Pi uses a real streaming Chat Completions client against a mocked provider response. All expectations use mock-only data and prices.

The Linux Docker bridge restriction is an infrastructural property of this particular Compose test. It does not establish isolation on different container runtimes, host network modes, custom task Compose overrides, privileged containers, attached Docker sockets, Kubernetes, or environments with altered firewall routing. Docker image tags in this smoke test are not digest-pinned. The test itself cannot establish absence of kernel/runtime vulnerabilities.

## Harbor mock integration status

The earlier Docker-only tests have been complemented by [a distinct isolated Harbor/Pi CI fixture](harbor-isolated.md). In this fixture the actual Harbor `main` task container is on an internal Docker network and uses a separate gateway connected to a fake provider network. Its runtime probes check gateway reachability and unsuccessful direct connections by provider DNS, provider raw IPv4, and public IPv4. The completed Pi transcript, task verifier outcome, mock-provider call count, and gateway ledger are audited together.

These observations establish the tested configuration's behavior. They do **not** constitute a general Harbor security proof, a provider-side billing guarantee, or evidence about arbitrary task Compose overrides. Production-key isolation, external billing reconciliation, and a real-model task remain outstanding.
