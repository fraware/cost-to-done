# Public upstream repair controls

Status: all four public controls passed in [run 45537928082](https://github.com/fraware/cost-to-done/actions/runs/45537928082). Eight Harbor nop controls and 32 local test executions completed, with assertion failures on each starter and zero failures on each reference. No model calls in that qualification run.

Four historical CPython defects form an initial external-source development
candidate set. Qualification runs independently per candidate:

| Task | Upstream issue | Starter | Reference |
| --- | --- | --- | --- |
| Grouped median return type | [#92531](https://github.com/python/cpython/issues/92531) | [5bc2390](https://github.com/python/cpython/commit/5bc2390229bbcb4f13359e867fd8a140a1d5496b) | [e01eeb7](https://github.com/python/cpython/commit/e01eeb7b4b8d00b9f5c6acb48957f46ac4e252c0) |
| Scoped IPv6 serialization | [#110196](https://github.com/python/cpython/issues/110196) | [b845a9e](https://github.com/python/cpython/commit/b845a9e145b2f133270aa07836c7e6a385066c00) | [767f416](https://github.com/python/cpython/commit/767f416feb551f495bacfff1e9ba1e6672c2f24e) |
| Fraction reflected power | [#119189](https://github.com/python/cpython/issues/119189) | [dae0375](https://github.com/python/cpython/commit/dae0375bd97f3821c5db1602a0653a3c5dc53c5b) | [b9965ef](https://github.com/python/cpython/commit/b9965ef282d6662145d2e05b080c811132ce6fde) |
| IPv4-mapped loopback | [#117566](https://github.com/python/cpython/issues/117566) | [eb20a7d](https://github.com/python/cpython/commit/eb20a7d12c4b2ab7931074843f8602a48b5b07bd) | [fb7f79b](https://github.com/python/cpython/commit/fb7f79b4da35b75cdc82ff3cf20816d2bf93d416) |

The preparation script fetches only the selected upstream module and license,
checks the Git blob IDs recorded from upstream trees, and commits those bytes
with identical project-authored regression tests into two local packaging
snapshots. Local packaging commits are distinct from upstream commits. Source
and license are retained together. The acceptance tests are derived from
public defect semantics, not the entire CPython test suite.

Run on a trusted host with Python 3.12, Git and Docker:

```bash
python -m pip install -e .
python -m pip install 'harbor==0.27.0'
python -m scripts.prepare_external_controls ./external-controls
```

Follow the [repository qualification guide](repository-task.md) for Harbor
nop controls and qualification. The dedicated workflow automates these steps
and archives provenance, staged manifests and qualification receipts.
Local regression controls must show assertion failures on the starter,
zero failures on the reference, and no test errors or skips in either case.

These tasks test external-source interoperability only. Their public fixes
and selected narrow regressions preclude claims of contamination resistance,
generalization, or full upstream-suite correctness. Neither the reference
source nor the verifier is proven adversarially inaccessible. No provider
credential is passed by this workflow.

## Screening exclusions

- [CPython #139065](https://github.com/python/cpython/issues/139065), textwrap
  trailing whitespace, starter 5c942f11cdf5f9d7313200983fa0c58b3bc670a2
  and reference 1c598e04361dbfc9cf465f3a02f83715c11b028c: the
  [original qualification run](https://github.com/fraware/cost-to-done/actions/runs/45536989491)
  failed during starter import because the selected module uses a regex
  escape unsupported in Python 3.12. Excluded from the Python 3.12 cohort;
  no source modification, model observation or accepted task failure.
  Reconsider only with a separately qualified newer runtime.

## Next gate

The [comparative protocol](comparative-protocol.md) remains the broader
experiment target. An initial 20-task, five-configuration, three-repetition
cohort (300 planned trials) is a proposed intermediate gate toward its
30-task target. It is not yet a frozen sampling frame or an authorized paid
experiment. Before selecting or running that cohort, define eligible
repositories, licensing, private holdout governance, difficulty and task-type
strata, fixed configuration identities, cost sources, retry policy and
precision/budget analysis. Record all screening exclusions. The public
controls above must not count toward a private holdout target.

## Fixed upstream development panel (experimental)

The separate [workflow](https://github.com/fraware/cost-to-done/actions/workflows/upstream-paid-pilot.yml)
prepares and requalifies the four exact public starters, checks the previously
observed task-input digests, and stages all 16 prospective Pi episodes before
reading any paid credential. Two native Responses configurations (GPT-6.1
Terra and GPT-6.2 Sol, both low effort) each receive two repetitions on each
task. The plan uses the existing dated rate cards, a fixed interleaved order,
one attempt per trial, five turns, 900 seconds, and $1 estimated admission
allowance per trial ($16 aggregate). Recheck prices and separately enforced
provider financial controls prior to a paid dispatch. These allowances are
not a verified provider hard cap.

PR and ordinary preflight execution do not use a paid credential. After
merge and successful preflight, a maintainer who has inspected and configured
provider financial controls may manually dispatch on canonical main using
`RUN-UPSTREAM-16` and the provider-limit review checkbox. A rerun of the
same workflow does not authorize inference. The existing fixed synthetic
pilot is separate. Arbitrary prepared task execution is still disabled.

The panel stops after the first unresolved result or identity mismatch.
Redacted artifacts retain planned trial IDs, intent records, available
estimates and unresolved or missing outcomes. Ratios are withheld unless
all planned observations are complete and matched; zero successful trials
has an undefined cost per completion. Public historical repairs and narrow
regression tests do not constitute a private holdout or independent
verifier replay. No invoice or general ranking claim follows.

## Reconstruct a panel report offline

Download the workflow artifact and extract it into a fresh directory. Use
a source checkout containing the audit script:

```bash
python -m pip install -e .
python -m scripts.audit_upstream_panel ./extracted-artifact \
  --output audit.json --html audit.html
```

Open the HTML file locally. The auditor checks upstream provenance pins,
qualification commitments, matching preflight and paid plans, and the
ordered intent/result records. It ignores the saved derived summary and
recomputes the counts and exact estimated cost numerator and success
denominator. An intent with no observation is distinguished from a trial
with no recorded intent. No missing cost is treated as zero. Unexpected
or duplicated records, non-prefix execution, changed identity commitments,
and costs without an observed ledger are rejected.

A preflight-only artifact yields an explicitly labeled report with no
paid observations or comparative ratios. An incomplete paid artifact
withholds all ratios. CI generates the review from the actual workflow
records and includes the JSON and offline HTML in its archive.

The review checks redacted record consistency; it does not authenticate
the original execution, establish a provider invoice, or re-execute the
candidate verifier. A valid report is not independent reproduction.

## Capture-enabled development panel (prospective schema v2)

A separate [capture/replay qualification workflow](https://github.com/fraware/cost-to-done/actions/workflows/upstream-replay.yml)
collects the exact single source module from each of the four defective
and repaired snapshots using Harbor nop. It then executes the original
regression tests in a fresh network-disabled, read-only, non-root Docker
container with no provider credential mounted. It checks the collected
source bytes against the known control bytes. This is a new qualification
gate, not an observed paid result.

The revised paid workflow requires all eight capture/replay controls before
any model access. The prospective plan schema is version 2, distinguished
from the earlier non-capture plan. Every completed original trial retains
its financial observation and a separate replay receipt bound to its raw
Harbor result digest, task digest, pristine test digest and runtime identity.
An unavailable replay or verdict disagreement stops further inference. Raw
candidate code and trial transcripts are not published. The replay checks
the selected module against the pristine narrow tests; arbitrary multi-file
changes, adversarial Python test manipulation, and container escape are not
established as safe or correct.

The offline auditor retains original-verifier accounting separately from
the count of recorded replay agreements. It rejects inconsistent replay
identity or status. Complete replay agreement requires all sixteen original
trials to have complete matched accounting and agreeing replay observations.
It does not re-execute the candidates or authenticate the receipts.
Historical schema v1 plans remain readable. No provider invoice is verified.
