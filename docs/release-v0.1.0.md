# Cost to Done v0.1.0

First alpha distribution of the local-first tools for measuring cost per verified completion.

## Try it

With Python 3.11–3.13 and an activated virtual environment:

```bash
python -m pip install https://github.com/fraware/cost-to-done/releases/download/v0.1.0/cost_to_done-0.1.0-py3-none-any.whl
cost-to-done demo --output demo.html
```

Open the generated report in your browser. No provider key or new inference is needed. The example data is synthetic. The release includes a wheel, source archive and SHA-256 checksum manifest.

Compare completed Harbor jobs:

```bash
cost-to-done compare-harbor fast=./jobs/fast careful=./jobs/careful --output comparison.html
```

## Included

- Offline receipt validation and failure-inclusive cost analysis.
- Matched Harbor job comparison and single-job evidence reports.
- Committed-file repository task packaging and starter/reference qualification.
- Experimental credential-isolated gateway for bundled tasks.
- Public experimental records, including an 18-trial development panel and a separate two-trial independent process replay cohort.

## Scope

This is an alpha, not a general-purpose hosted benchmark or a production sandbox. Real monetary observations are rate-card estimates, not reconciled provider invoices. External paid execution is restricted to a separately authorized fixed synthetic pilot. Arbitrary paid external repositories are unsupported. The original public experiments are small development cohorts, not a general model ranking.

See the [project documentation](https://github.com/fraware/cost-to-done/tree/main/docs), [security policy](https://github.com/fraware/cost-to-done/blob/main/SECURITY.md), and [issue tracker](https://github.com/fraware/cost-to-done/issues).
