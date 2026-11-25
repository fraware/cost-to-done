# Public upstream repair controls

Status: qualification pending CI. No model calls, no paid execution, no new
cost or model-performance observations.

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
