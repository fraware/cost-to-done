# Harbor importer: experimental contract

Harbor is an upstream framework from the Terminal-Bench creators. The integration consumes already-generated `trials/*/result.json` files. Harbor handles agent execution; Cost to Done handles a normalized report. Inspect the upstream [Harbor documentation](https://github.com/harbor-framework/harbor) for current setup and CLI commands.

This converter targets the published Harbor `TrialResult` schema v1, `AgentContext.cost_usd`, `VerifierResult.rewards`, and wall-clock `started_at`/`finished_at` fields. Harbor 0.26.0 trial files from an actual Docker-backed no-op/oracle control were inspected on November 20, 2026. Their directory layout and schemas are covered by recorded-fixture tests. Importing *paid-model economic results* remains unverified, since both control agents report null cost.

## Required manifest

Create a JSON file next to the Harbor job folders. Each job is one pinned agent+model configuration with one independently graded attempt per task. The importer does not infer identity or safe retry boundaries from loosely coupled folder names.

```json
{
  "schema_version": 1,
  "tasks": {
    "repair-1": {
      "harbor_task_checksum": "EXACT_CHECKSUM_FROM_HARBOR",
      "task_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "verifier_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "reward_key": "reward"
    }
  },
  "jobs": [
    {
      "path": "jobs/experiment-model-a",
      "configuration_id": "pi+provider/model-a@settings",
      "agent": "pi",
      "model": "provider/model-a",
      "harness_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "retry_policy": "independent-trials",
      "n_attempts": 1,
      "expected_tasks": ["repair-1"],
      "agent_version": "1.0.0"
    }
  ]
}
```

Replace every placeholder with the measured job's identity and **real artifact digests**. Placeholder hashes in this documentation demonstrate syntax only. A task's `harbor_task_checksum` must equal the result file's recorded checksum. Artifact digests are user assertions here, not verified against local file bytes. The manifest itself belongs in the published evidence bundle and must identify how its digests were produced.

## Import and report

```bash
cost-to-done import-harbor manifest.json --output receipts.jsonl
cost-to-done validate receipts.jsonl
cost-to-done report receipts.jsonl --output results.html
```

The importer accepts both the current Harbor 0.26 `<job>/<trial>/result.json` layout and the older `<job>/trials/<trial>/result.json` layout. Supply `expected_tasks` to ensure that omissions are detected, and `agent_version` to verify that the harness revision matches the pin. Directly provided job directories are restricted to descendants of the manifest directory, preventing traversal out of the evidence root.

The importer refuses absent or invalid cost data. An exception or missing verifier result counts as an infrastructure error; a complete reward equal to 1 counts as a pass. Partial rewards fail the binary pass condition. Source costs are labeled `rate_card_estimate` since Harbor's `AgentContext.cost_usd` is agent-reported, not independent billing evidence.

**Security:** Only import trusted local job directories. The importer does not invoke an agent or execute code, yet job outputs and manifest contents are untrusted data. Do not treat this conversion as an attestation, cost invoice, independent audit, or published benchmark.

## Known limits

- This adapter cannot import entire jobs with omitted trial cost data, incomplete job rows, or incompatible harness settings.
- It does not reconstruct prompt caching, tool billing, price table versions, or provider invoice reconciliation.
- It does not cryptographically verify that a verifier binary was invoked, or that an agent was isolated from test answers.
- A multistep Harbor result is supported for cost accumulation only where each step includes complete `cost_usd` data; the terminal trial's verifier result is used for pass/fail.
- Full task-panel equality and replication counts are enforced by the downstream analyzer. A manifest mismatch terminates the import.

## Inspect a job without preparing a manifest

The read-only inspector accepts a genuine Harbor job directory and shows the
recorded verdict and provenance for each trial, as well as whether agent cost
telemetry is available:

```bash
cost-to-done inspect-harbor control-jobs/controls-oracle
```

It reports document SHA-256 digests and checks the job's declared trial count
against the discovered result files. `billing_verified` and
`verifier_independently_audited` are deliberately `false`. If the model/agent
reported no cost, the field is `null` and the status is `unavailable`.
The inspector never calls a provider or executes task code. Inspect only
trusted local result directories; job artifacts and trajectories can contain
sensitive information.
