# Harbor importer: experimental contract

Harbor is an upstream framework from the Terminal-Bench creators. The integration consumes already-generated `trials/*/result.json` files. Harbor handles agent execution; Cost to Done handles a normalized report. Inspect the upstream [Harbor documentation](https://github.com/harbor-framework/harbor) for current setup and CLI commands.

This initial converter targets the published Harbor `TrialResult` schema v1, `AgentContext.cost_usd`, `VerifierResult.rewards`, and wall-clock `started_at`/`finished_at` fields. We have only tested artificial Harbor-shaped fixtures; compatibility with actual Harbor job outputs is **unverified**.

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
      "n_attempts": 1
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

The importer refuses absent or invalid cost data. An exception or missing verifier result counts as an infrastructure error; a complete reward equal to 1 counts as a pass. Partial rewards fail the binary pass condition. Source costs are labeled `rate_card_estimate` since Harbor's `AgentContext.cost_usd` is agent-reported, not independent billing evidence.

**Security:** Only import trusted local job directories. The importer does not invoke an agent or execute code, yet job outputs and manifest contents are untrusted data. Do not treat this conversion as an attestation, cost invoice, independent audit, or published benchmark.

## Known limits

- This adapter cannot import entire jobs with omitted trial cost data, incomplete job rows, or incompatible harness settings.
- It does not reconstruct prompt caching, tool billing, price table versions, or provider invoice reconciliation.
- It does not cryptographically verify that a verifier binary was invoked, or that an agent was isolated from test answers.
- A multistep Harbor result is supported for cost accumulation only where each step includes complete `cost_usd` data; the terminal trial's verifier result is used for pass/fail.
- Full task-panel equality and replication counts are enforced by the downstream analyzer. A manifest mismatch terminates the import.
