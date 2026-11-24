# Initial comparative experiment: protocol and release gates

Status: proposed; no new model observations. The allocation repair and the
two new tasks (interval union and dependency ordering) are development
fixtures, not a representative held-out software engineering benchmark.
All tasks and reference solutions are public. Do not interpret these tasks as
contamination-resistant or general developer workloads.

## Stage A: qualify infrastructure and tasks

For every task, freeze the task tree, acceptance tests, environment image
digest, Harbor and Pi versions. Run untouched starter and oracle in independent
workspaces; require negative and positive controls locally and in Harbor.
The new tasks are not admitted to the credential-isolated paid runner until
its trusted task allowlist and environment packaging support them explicitly.

## Stage B: paired paid pilot

After native Responses protocol and isolated reasoning-enabled rehearsal pass,
run GPT-6.1 Terra and GPT-6.2 Sol on the same qualified allocation task using
the same agent, API, reasoning-effort setting, output cap, tool policy,
wall-clock limit and turn budget. Use one trial per configuration for protocol
qualification, never as a ranking. Record API-reported model identity,
price-schedule identity, actual verifier verdict, all requests, settlement,
uncertainties and errors. Preserve independent verifier replay artifacts under
appropriate access restrictions. Do not drop failures or unresolved costs.

## Stage C: broader benchmark

Pre-register a task sampling frame including repository-origin issues and
privately held-out tasks with documented permissions. Target 30 distinct tasks
and three repetitions for each of five configurations (450 planned trials),
subject to a pilot-based precision and budget analysis. Freeze task and
configuration manifests and balanced randomized run order before scoring.
Treat model+harness+protocol+effort as configurations, not isolated model effects.
No substitution after inspecting results. Keep provider failures and missing
outcomes separate from valid task failures; report their counts and all known
expenditure. Withhold point comparisons when unresolved financial liabilities
or incompatible task supports invalidate the accounting contract.

Primary estimand: total rate-card-estimated expenditure divided by successful
verified trials for each configuration on the same task/repetition support.
Report completion fraction, cost distributions, paired task differences,
wall time, and task-cluster bootstrap uncertainty. If zero tasks pass, cost per
completion is undefined. Cached input pricing, provider invoice reconciliation
and human-review expense require separate declared accounting policies.

## Release gate

Publish the evidence bundle, executable verifier replay, pinned versions and
limitations alongside a reproducible CLI quickstart. Distinguish synthetic
examples, development pilots, held-out estimates and billed amounts. Do not
assert an economic reversal or announce a winning configuration unless the
results justify it. Keep current evidence accessible on the landing page.

## Development-panel expansion

Three bundled fixtures passed separate local and Harbor negative/positive
controls (45313687642). The native runner now stages only their declared
single-module files and uses a fixed trusted Pi installation template with a
module-specific COPY instruction. No arbitrary repository or task directories
are supported. The original allocation fixture remains the default.

The new expanded native mock workflow qualifies each additional task through
Pi and the credential-isolated gateway, including low-effort opaque reasoning
replay and the independent task verifier. Its scripted repairs and fictional
usage are not model performance measurements. Paid matrix execution is a
separate gate after both the frontier pilot and the expanded mock checks pass.

## Freeze the development-panel plan (zero spend)

```bash
cost-to-done plan-panel --output panel.json
cost-to-done plan-panel --repetitions 3 --max-total-usd 18 --output panel-18.json
```

The default plan lists six episodes (three public tasks, two native low-effort
configurations, one repetition). The larger plan lists eighteen. Task/repetition
blocks are shuffled with a declared seed, and configuration order alternates
across blocks. Each plan includes content hashes of the actual staged task files,
the generated Dockerfile, runner source files, price schedules and the complete
prospective plan. The summed local admission allowances must fit the explicit
aggregate ceiling. This is a planning artifact only: the CLI does not execute
inference, validate provider billing, or establish a hard invoice cap.

## Execute the bounded development panel

PR qualification runs all three reasoning-enabled mock tasks. On the first
trusted-main push of the dedicated development-panel workflow, the paid job
runs only after those checks pass. It freezes the 18-episode plan, executes
serially in its predeclared order, uses fresh dedicated ledgers and stops on
unresolved execution or financial state. Missing trials remain explicit.
The $18 sum is an estimated admission allowance, not a provider hard cap.
No automated retry of the paid workflow is authorized. The plan and redacted
attestations are archived; raw private workspaces and logs are excluded.
Cost-per-completion ratios are withheld if task support, checksum identity,
verifier outcomes or financial settlement are incomplete. This is public-task
development evidence only; independent verifier replay remains outstanding.

Recompute the accounting from downloaded evidence, even after an interrupted
run whose derived summary is absent:

```bash
cost-to-done summarize-panel path/to/extracted-panel --output audited-summary.json
```

This checks declared identities and matching support, not authenticity of the
execution or the provider invoice. It refuses duplicate raw trial hashes.

Use `cost-to-done report-panel path/to/extracted-panel --output panel-report.html`
for a standalone offline review. The manifest must contain the complete
Cartesian task/configuration/repetition support; a recomputed self-declared
hash alone does not establish that property. Reports show every planned
episode, include known charges from failed trials, and never treat missing
records as free executions. No model ranking is produced.

The first matched panel completed all eighteen paid episodes. See [the recorded observations](development-panel-observations.md) for the original workflow, individual log observations and interpretation limits.
