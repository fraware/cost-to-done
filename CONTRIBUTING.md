# Contributing to Cost to Done

The project measures the economics of accepted AI work. Contributions should improve developer utility, measurement validity, reproducibility or the clarity of evidence.

## Set up

Use Python 3.11–3.13 and a virtual environment. The local tools have no runtime package dependencies.

```bash
git clone https://github.com/fraware/cost-to-done.git
cd cost-to-done
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The Python suite uses fictional provider fixtures. Do not supply real API keys for routine development. Container integration tests need Docker and the pinned Harbor/Pi environment documented in [the relevant guides](docs/README.md).

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/cost_to_done/` | Receipt validation, reports, Harbor adapters, metering and experimental execution |
| `tasks/` | Public repair tasks, acceptance tests and reference solutions |
| `experiments/live/` | Trusted execution templates and dated price schedules |
| `scripts/` | Reproducibility, controls, audit and experiment orchestration |
| `tests/` | Regression tests and fictional-provider integration fixtures |
| `evidence/` | Preserved redacted historical experimental observations |
| `docs/` | User guides, experimental protocols and static site |

## Submit a change

Open an issue for a new measurement contract or significant execution change. For a bug fix, include a reproducer and focused regression test. In a pull request, explain the affected behavior, test scope, and any changes to trust boundaries or experimental comparability.

Preserve existing historical observations and frozen source identities. A corrected implementation must not silently rewrite an earlier cohort. New empirical claims need a predeclared protocol, raw evidence linkage and an explicit accounting basis. Mock results must be identified as fictional.

Review [security](SECURITY.md) before touching credentials, subprocesses, network policies or verifiers. Never commit credentials, private traces, proprietary source or personal data. Do not trigger paid workflows as part of routine CI.

Documentation changes should use commands supported by the current CLI and valid repository-relative links. The website browser workflow exercises all three public HTML pages at four viewport widths.

A passing test establishes tested behavior, not a general empirical claim about models.
