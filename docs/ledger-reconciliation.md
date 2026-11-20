# Reconcile a Harbor trial with a dedicated inference ledger

`cost-to-done reconcile-harbor` joins a **single complete Harbor trial** and a **single dedicated gateway ledger** into one canonical Cost to Done receipt. The output consists of a JSONL trial receipt and a separate provenance document. Both are generated offline, without contacting any model provider.

This tool addresses a specific accounting problem. An inference run contains one or more model requests, while a trial is counted as **one task attempt**. Multiple tool-use/model turns contribute to that attempt's total expenditure; they must never be counted as multiple independent verified completions.

## Example

The first CI integration uses a fake model and fictional price schedule. The synthetic schedule is stored in [`tests/fixtures/mock-price-schedule.json`](../tests/fixtures/mock-price-schedule.json).

```bash
# Capture the task checksum from a completed, isolated Harbor job.
cost-to-done inspect-harbor path/to/harbor-job

# Compute an explicit digest for the precise harness configuration.
# The caller is responsible for comprehensive harness provenance.
sha256sum tests/harbor/compose-isolated.yaml

cost-to-done reconcile-harbor \
  --job path/to/harbor-job \
  --ledger path/to/gateway.sqlite3 \
  --task path/to/qualifying-task-copy \
  --verifier path/to/qualifying-task-copy/tests/test_state.py \
  --price-schedule tests/fixtures/mock-price-schedule.json \
  --model openai/test-model-1 --agent pi \
  --configuration-id pi-0.85.1-mock \
  --harness-digest 64_LOWERCASE_HEX_CHARACTERS \
  --harbor-task-checksum 40_LOWERCASE_HEX_CHARACTERS \
  --output receipt.jsonl

cost-to-done validate receipt.jsonl
```

A successful run writes `receipt.jsonl` and `receipt.jsonl.evidence.json`. The example placeholders are deliberately not purported measurement identifiers. The CI workflow computes and checks its own actual values.

## Admission criteria

The importer rejects incomplete or multiple-trial Harbor jobs, mismatched task/model/agent identifiers, invalid durations, a ledger with pending/uncertain liabilities, unsettled requests, a breached budget, a mismatched price-schedule hash, zero or inconsistent totals, unsafe task/verifier paths, and pre-existing output files. It hashes the locally supplied task and verifier artifact bytes. The caller must dedicate one gateway and ledger to exactly one evaluated trial.

It attributes the **sum of all settled model requests** to one task attempt and records the number and identifiers of those requests separately. The canonical receipt uses `rate_card_estimate`, never `billed`, because provider-reported usage, payment settlement, invoice line items, tool expenses and subscription allocations are outside this tool's evidence.

## Evidence boundaries

- The verifier's local source bytes are hashed; this does not prove that the same hidden verifier ran in the container. The Harbor task checksum is also checked against the operator-supplied expected value, not independently recomputed from Harbor's task packaging logic.
- The harness digest is operator-declared. The importer does not authenticate Docker images, model weights, the gateway binary, or container networking.
- The current gateway ledger lacks cryptographically signed request-to-trial attribution. Joining its entries to a Harbor trial depends on **dedicated-ledger isolation asserted by the operator**. Reuse of a gateway ledger across trials invalidates this attribution.
- A nominally settled ledger reflects **rate-card estimates**, not actual provider bills. Real invoice reconciliation must separately match request-level usage and all billable categories.
- Synthetic fixtures remain synthetic evidence even if a real agent client and executable verifier processed them. The importer does not attempt to infer whether the model endpoint was a mock or a commercial provider.
- The two output files are each written using a replace operation; there is no atomic two-file transaction. Consumers must require both and independently verify their hashes and identities before publishing claims.

The eventual public model leaderboard must apply stronger evidence rules before treating any result as independently reproduced.
