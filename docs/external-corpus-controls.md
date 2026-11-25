# Public upstream repair controls

Status: qualification pending CI. No model calls, no paid execution, no new
cost or model-performance observations.

Two historical CPython defects form an initial external-source development
cohort:

| Task | Upstream issue | Starter | Reference |
| --- | --- | --- | --- |
| textwrap trailing whitespace | [#139065](https://github.com/python/cpython/issues/139065) | [5c942f1](https://github.com/python/cpython/commit/5c942f11cdf5f9d7313200983fa0c58b3bc670a2) | [1c598e0](https://github.com/python/cpython/commit/1c598e04361dbfc9cf465f3a02f83715c11b028c) |
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

## Next gate

The [comparative protocol](comparative-protocol.md) remains the broader
experiment target. An initial 20-task, five-configuration, three-repetition
cohort (300 planned trials) is a proposed intermediate gate toward its
30-task target. It is not yet a frozen sampling frame or an authorized paid
experiment. Before selecting or running that cohort, define eligible
repositories, licensing, private holdout governance, difficulty and task-type
strata, fixed configuration identities, cost sources, retry policy and
precision/budget analysis. Record all screening exclusions. The two public
controls above must not count toward a private holdout target.
