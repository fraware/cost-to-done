# First real-provider trial diagnosis

GitHub Actions run 45307609892 exercised Harbor 0.27.0 and Pi 0.85.1 using
real OpenAI API access through the dedicated gateway. The provider-facing
gateway recorded **four uncertain requests per model**. Its SQLite ledger
did not settle a usage-based estimate, and Harbor reported failure for the
allocation-repair task in both cases.

These results do **not** establish zero provider charges. They also do not
establish a model-quality difference; both runs share an unresolved protocol
or metering failure. The uploaded redacted attestations document task
checksums, observed outcomes, unresolved request counts, and rate schedule
identities, omitting raw prompts and provider secrets.

The controlled diagnostic in
`.github/workflows/openai-protocol-diagnostic.yml` performs one small, real
Chat Completions request per model through the same validated gateway
request/accounting path. It captures only HTTP status, sanitized provider
error category and parameter, returned model identifier, terminal usage
parser status, and ledger settlement or uncertainty. Model output and raw
provider error messages are never published.

The diagnostic is **paid**, uses a separate internal USD 0.25 estimate allowance
per model, and consumes the repository-scoped `OPENAI_API_KEY` on trusted
`main`. That allowance is not a hard provider invoice cap. The result
supports protocol debugging only, not general benchmarking.

When the provider incompatibility is resolved, we must requalify the first
genuine repair under pinned task/environment/verifier conditions and preserve
the raw restricted evidence alongside independently reconciled billing.
