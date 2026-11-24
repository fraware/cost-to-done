# Getting started

Start with the local reporting tools. They do not execute repository source, require an API key, or install Harbor.

## Install the alpha release

Python 3.11–3.13 is covered by the current Linux CI matrix. Use a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install https://github.com/fraware/cost-to-done/releases/download/v0.1.0/cost_to_done-0.1.0-py3-none-any.whl
cost-to-done --help
```

For Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1`. Windows installation and filesystem behavior are not currently qualified by CI.

The [v0.1.0 alpha release](https://github.com/fraware/cost-to-done/releases/tag/v0.1.0) includes the wheel, source archive and SHA-256 manifest. To verify downloaded distributions, place them and `SHA256SUMS` in the same directory and run `sha256sum -c SHA256SUMS` on Linux. Both distributions passed installation tests outside the checkout. The project is not published on PyPI.

For development or to run the checkout-only experiment scripts:

```bash
git clone https://github.com/fraware/cost-to-done.git
cd cost-to-done
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Generate your first report

```bash
cost-to-done demo --output demo.html
```

Open the generated file locally. It contains synthetic receipts, not measured model results. No network is required to render it. Choose a new output path on each invocation: the exporter rejects overwrites and requires a destination filesystem supporting hard links.

## Compare existing Harbor jobs

```bash
cost-to-done compare-harbor fast=./jobs/fast careful=./jobs/careful \
  --output comparison.html
```

Replace both paths with completed Harbor job directories. The report checks matched task identifiers and checksums. Missing agent-reported cost remains unavailable; the comparison does not rank models or independently execute tests. See [the full guide](compare-harbor.md).

For one job:

```bash
cost-to-done report-harbor ./jobs/fast --output evidence.html
```

## Analyze JSONL receipts

Generate the included example from the checkout:

```bash
python examples/generate_synthetic.py
cost-to-done validate examples/synthetic-trials.jsonl
cost-to-done report examples/synthetic-trials.jsonl \
  --output synthetic-report.html --demo
```

For your own complete receipts, use the same commands with your private input path and omit `--demo`. Read [the methodology](methodology.md) before interpreting ratios. Input consistency does not establish authentic billed costs or verifier execution.

## Prepare your repository

Follow [the repository task walkthrough](repository-task.md) to package selected committed Python files and unittest acceptance tests. Qualification uses a known defective starter and a correct reference. General-purpose paid external execution is disabled.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found | Activate the environment and reinstall from the checkout; alternatively invoke `python -m cost_to_done`. |
| Output already exists | Choose a fresh output path. Do not delete evidence solely to repeat a command. |
| Missing parent directory | Create the intended output parent first. |
| Harbor task mismatch | Confirm both runs evaluated exactly the same task inputs; do not rewrite checksums to force a comparison. |
| Missing cost | Inspect the original telemetry. Do not substitute zero. |
| Zero successful tasks | Cost per completion is undefined. Inspect total expenditure and failure outcomes. |

For execution prerequisites and credentials, see [the live runner guide](live-gateway.md) and [security policy](../SECURITY.md).
