# Zero-spend OpenAI credential preflight

The **model-access metadata check** uses the official read-only
`GET /v1/models/{model}` endpoint on `api.openai.com`.
It does **not** invoke model inference, spend tokens, or reconcile provider bills.
Metadata availability is not a guarantee that inference will succeed.

The workflow `.github/workflows/openai-access-preflight.yml` executes only
from the repository's trusted `main` branch. It reads a repository-scoped secret
named `OPENAI_API_KEY` in the isolated GitHub Actions runner. The credential
is never printed, committed, or uploaded as an artifact. Provider errors are
reduced to fixed status labels. HTTPS redirects are never followed.

If the repository secret does not exist, the result is
`repository_secret_unavailable` and no request is made. A secret stored
in another repository, ChatGPT account, or external service is not implicitly
available to this workflow.

## Local use

In a Python 3.11+ installation of Cost to Done, store the key in a regular
mode-0600 file outside the repository. Then run:

```python
from pathlib import Path
from cost_to_done.provider_probe import probe_models

result = probe_models(
    Path("/secure/outside-checkout/openai.key"),
    ("gpt-6.1-terra", "gpt-6.2-sol"),
)
print(result)
```

The probe's success criterion is a model metadata response for the requested
exact identifier. It does not measure task success, complete spend, or provider
spending limits. A real evaluation still needs explicit trial authorization,
a verified price schedule, and a separate provider-side spending decision.

Reference: https://developers.openai.com/api/reference/resources/models/methods/retrieve/
