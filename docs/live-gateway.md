# First real-model trial through the isolated gateway

**Status (24 November 2026):** Experimental execution route. Deterministic mock controls and bounded paid Chat Completions and native Responses trials have completed. See [first paid observations](first-real-observations.md), [native pilot](frontier-observations.md), [development panel](development-panel-observations.md) and [separate replay cohort](real-candidate-replay-observations.md). All costs are local estimates; provider invoices and general sandbox security have not been independently verified.

The purpose of `run-harbor-gateway` is to obtain **one privately inspected, verifiable software-repair trial** while limiting the upstream API credential to a gateway container. The public paid command supports the three bundled qualified tasks (`allocation-repair`, `dependency-order-repair`, `interval-union-repair`). See [repository task scope](repository-task.md) for the separate external rehearsal and fixed pilot. The agent executes inside Docker's internal-only network and receives a disposable gateway token; the upstream credential is a Docker Compose file secret exposed only to the gateway service.

## Preconditions

- Linux containers under a trusted, current Docker Engine and Docker Compose v2, on a host that you administer. Do not attach privileged containers, a Docker socket, or arbitrary Compose overrides.
- Python 3.12+, `harbor==0.27.0`, and Cost to Done installed from a pinned repository revision. The task image installs Pi 0.85.1 at build time. npm transitive dependencies are not hermetically pinned.
- One supported exact OpenAI model ID and a dated pricing schedule with the matching identifier. The CLI accepts `--api chat` (default) or `--api responses`. GPT-6.1 Terra and GPT-6.2 Sol/Astra tool-calling routes require native Responses; the incompatible Chat Completions route is rejected at preflight. Terra and Sol have been exercised at `--api responses --reasoning-effort low`; Astra has not been qualified by these paid trials. GPT-5.4 and GPT-5.4 mini use explicit `reasoning_effort=none` for Chat Completions function tools; see [model compatibility](model-compatibility.md). Check current pricing and endpoint compatibility independently. The gateway declines unknown fields, unsupported modalities, and missing terminal token usage.
- A **dedicated provider project with a separately enforced financial limit**, configured and inspected by the operator. For OpenAI API projects, open **Project → Limits**, set the monthly spend limit, and explicitly enable **Enforce a hard limit**. A budget alert alone does not block traffic. Enforcement is not instantaneous and recorded spending can slightly exceed the threshold ([official instructions](https://help.openai.com/en/articles/9186755-managing-projects-in-the-api-platform)). Gateway reservations are **estimates** and the CLI cannot inspect or create provider limits.
- A private credential file outside this repository and outside the run directory, mode 0600. Place the upstream key in the file as its only line. Never copy its contents into shell arguments, source control, a GitHub Actions secret used by public PRs, or task input.

## 1. Prepare the private key and dated price schedule

Create `~/.config/cost-to-done/upstream-key` with mode 0600 using a local password manager or a secure editor. Do not echo a key into your shell history. Its path is passed to the CLI; its contents are mounted only into the gateway container.

Create a price-schedule JSON file from the current **official provider price page**, using the exact model identifier that the provider returns. Fields:

```json
{
  "model": "YOUR_EXACT_CHAT_COMPLETIONS_MODEL_ID",
  "effective_date": "2026-11-20",
  "source_url": "https://platform.openai.com/docs/pricing",
  "input_per_million_usd": "REPLACE_WITH_VERIFIED_DECIMAL",
  "output_per_million_usd": "REPLACE_WITH_VERIFIED_DECIMAL"
}
```

All numeric prices must be nonnegative decimal **strings**, with a valid numeric value replacing each placeholder. Record discounts, caching rules, tools, retries, and omitted billing categories separately. The two-rate contract is suitable only for supported text-only usage billed by input/output tokens. This example does not assert a particular model's pricing or availability.

## 2. Produce the zero-spend execution plan

From the repository root:

```bash
python -m pip install -e .
python -m pip install 'harbor==0.27.0'

cost-to-done run-harbor-gateway \
  --model YOUR_EXACT_CHAT_COMPLETIONS_MODEL_ID \
  --price-schedule /absolute/path/to/prices.json \
  --provider-key-file "$HOME/.config/cost-to-done/upstream-key" \
  --budget-usd 0.25 \
  --job-name gateway-smoke-01
```

This mode does **not** read the key file, run Docker, make provider calls, or create output directories. It verifies task/model/price-schedule consistency and prints a plan. Set the `--budget-usd` value to a spending allowance that **has also been restricted by the provider-side controls**; the admission budget itself is not a provider hard cap.

## 3. Explicitly execute one attempt

Only on your trusted host, once external account restrictions are confirmed:

```bash
cost-to-done run-harbor-gateway \
  --model YOUR_EXACT_CHAT_COMPLETIONS_MODEL_ID \
  --price-schedule /absolute/path/to/prices.json \
  --provider-key-file "$HOME/.config/cost-to-done/upstream-key" \
  --budget-usd 0.25 \
  --job-name gateway-smoke-01 \
  --max-turns 3 --max-wall-seconds 900 \
  --execute --acknowledge-provider-limit
```

The runner first validates the combined Docker Compose configuration and **refuses to start the model trial** if the agent would gain provider-network access, the upstream key could mount into the agent, host ports are published, or unapproved services or capabilities appear. This preflight is a configuration check, not a proof of the dynamic Harbor runtime.

The runner copies the known task to a private session directory, substitutes the pinned Pi image, generates a fresh gateway token, and starts one Harbor trial. The gateway service runs with the invoking host user\'s numeric UID/GID. This matches the owner of the chmod-0600 provider-key file and chmod-0700 evidence directory while retaining dropped Linux capabilities. Do not run this experimental launcher as host root. A minimal environment is passed to Harbor and **the upstream key is omitted from that environment**. A dedicated Compose secret mounts the key in `ctd_gateway`; `main` stays solely on `ctd_agent_net` with `internal: true`. No service publishes a host port.

Pi receives the gateway token for `http://ctd_gateway:8866/v1` and is capped at three completed turns and 4,096 generated tokens per request. The gateway validates model identity and reserves a conservative estimated charge for each forwarded request in a per-run SQLite ledger. The task verifier grades the resulting patch independently of the model response. Harbor's end-to-end runtime and reported usage are recorded.

**Operational limitation:** The timed Harbor process could leave detached containers or in-flight provider calls. The ledger retains ambiguous reservations. Stop any leftover services, revoke the disposable provider key if necessary, check the provider's usage dashboard, and reconcile invoices independently. A green verifier and settled ledger are not independent proof of an invoice amount.

## 4. Inspect privately and reconcile

The runner writes `runs/.sessions/gateway-smoke-01/run-summary.json`, a private driver log, the copied task, and the gateway SQLite ledger. Harbor writes its trial under `runs/gateway-smoke-01/`.

```bash
cost-to-done inspect-harbor runs/gateway-smoke-01
cost-to-done gateway-status runs/.sessions/gateway-smoke-01/evidence/ledger.sqlite3
```

The summary labels expenses as **unverified rate-card estimates**, records the price schedule digest and full ledger entries, and does not assert actual billed dollars. If usage is absent, the gateway request fails, the run is incomplete, or reservations remain uncertain, do not convert the run into a success-cost data point. Compare the provider's independent usage and billing records before publication.

A canonical local receipt is generated separately with `cost-to-done reconcile-harbor`, once the task/image identity and dedicated-ledger attribution have been independently checked. See [Ledger reconciliation](ledger-reconciliation.md). Do not upload raw logs, prompts, source patches, keys, or container environment dumps without review.

## Verified scope and outstanding work

The live route has static topology checks, price-schedule validation, credential-scope tests, simulated process tests and tests for authorization failures. Paid CI trials and a three-task matched development panel have completed; the separate candidate-replay cohort tested agreement in fresh offline verifier processes. Neither these trials nor the mock network probes establish adversarial sandbox integrity, a provider-enforced billing cap, invoice reconciliation or performance on unseen repositories. The next empirical gate is an independently cost-reconciled external task comparison.

## Offline acceptance test

The [credential-isolated live-runner rehearsal](live-rehearsal.md) exercises this execution route against a fake provider in GitHub Actions. The test preserves the provider-secret mount and agent network declaration; its upstream transport and additional bypass probes are test-only. It does not attest to commercial-provider reachability or actual charges.
