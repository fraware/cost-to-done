# Flagship study: prospective design gate

Status: design tooling only. No held-out tasks, qualified five-configuration
matrix, provider authorization, or new model observations are asserted.

The intermediate target is 20 independently sourced tasks, five configurations
and three repetitions (300 planned trials), ahead of the 30-task target in
the [comparative protocol](comparative-protocol.md). The public upstream
development controls are not private holdouts.

## Sampling and selection

Recruit repository owners or authorized maintainers to supply defects with a
known correct reference, executable acceptance tests and permission to conduct
the evaluation and publish agreed redacted evidence. Screen before any model
trial. Record every screened candidate, exclusion and reason, provenance,
runtime, dependency and license obligations, negative and positive controls,
verifier review, and prior-publication or exposure risk. No replacement based
on measured model outcomes. Preserve permission and exposure records privately.

The initial design allocates five tasks to each of four functional strata:
algorithmic behavior, state transitions, parsing/validation, and integration.
Assign a primary stratum before running controls; these categories are not
difficulty labels. Use at least five repository groups with at most four tasks
per group. This purposive panel is not a random sample of all coding work.

## Configuration and accounting freeze

Select five exact model/agent/protocol/effort configurations only after
route-specific compatibility, rate schedules and metering have been checked.
Freeze model identifiers, agent versions, runtime images, source digests,
settings, wall-clock and turn limits, retry policy, and analysis protocol.
An equal estimated admission allowance applies to all trials. Before
execution, separately inspect provider limits and perform an isolation and
billing review. Estimated admission sums are not actual invoice limits.

## Generate a local prospective schedule

```bash
python -m pip install -e .
python -m scripts.plan_flagship private/design.json --output private/plan.json
```

Input schema (field descriptions; not an executable or filled manifest):

| Field | Required value |
| --- | --- |
| schema_version | integer 1 |
| seed | uint32 |
| tasks | twenty task objects |
| configurations | five configuration objects |
| screening_log_sha256 | digest of the frozen screening log |
| harness_sha256 | digest of complete harness manifest |
| retry_policy_sha256 | digest of frozen retry policy |
| analysis_protocol_sha256 | digest of frozen statistical plan |
| allowance_per_trial_usd | positive exact decimal string |
| max_total_usd | positive exact decimal string, at least 300 allowances |

Each task object contains exactly id, repository_group, stratum,
task_input_sha256, qualification_sha256, permission_record_sha256, and
holdout_record_sha256. Each configuration object contains exactly id, model,
configuration_sha256, price_schedule_sha256, and route_qualification_sha256.
Identifiers are lowercase ASCII letters, digits or hyphens, beginning with a
letter, two to 48 characters. Digests are lowercase 64-character SHA-256 hex.
Use opaque IDs for private repositories and keep sensitive records offline.
A digest of a low-entropy secret does not establish confidentiality.

The planner rejects repeated task/qualification/configuration commitments,
missing fields, insufficient repository coverage, unbalanced strata, and
insufficient aggregate admission allowance. It generates all 300 distinct
task/configuration/repetition identities, interleaved in sixty matched blocks.
Ten Williams-design orders appear six times each. Each configuration appears
twelve times in each position, and each directed adjacent configuration pair
occurs twelve times within blocks. The seed deterministically orders blocks
and permutations. Actual time-dependent service behavior is not controlled
by this ordering.

The plan validates structural consistency only. It neither verifies the
referenced records nor opens provider access. Preserve its digest and the
complete referenced private artifacts prospectively. A synthetic fixture in
the test suite is not a real study plan.

## Analysis and release gates

Report all planned support, missing and unresolved trials, costs of failed
trials, complete financial coverage, and paired configuration results.
Withhold ratios for unresolved support or costs; zero successes yields an
undefined ratio. Estimate paired task-level uncertainty accounting for
repository clustering (with five or more groups, cluster-based intervals
may be unstable); report sensitivity to task/repository weighting and
retry policy. Select the final interval procedure and precision target
prospectively. No success or price-order reversal is promised.

Execution remains blocked until the actual corpus, permissions, reference
controls, verifier review, five routes, budget and analysis are independently
reviewed. This script has no executor or provider access.
