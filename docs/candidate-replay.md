# Independent candidate replay: qualification

The prior paid pilots and 18-trial development-panel workflow use historical
inputs and publish redacted Harbor outcome attestations. They do not preserve
a candidate source artifact for independent replay. No replay claim is made
about those observations.

The new mock-only qualification adds an explicit Harbor 0.27.0 artifact
declaration to a disposable task copy. It captures the final module and
checks the collection manifest before staging the file with the pristine
repository verifier in a fresh pinned Docker container. The container runs as
an unprivileged user, with no network, a read-only filesystem and input mounts,
dropped capabilities, process and memory limits and bounded wall time. No
provider key or gateway is mounted. The same verifier is run against the
unchanged starter as a negative control.

The replay module records the source and verifier SHA-256 identities,
runtime image and cleanup result. Raw generated source is untrusted. The
test process shares Python runtime state with the candidate; passing tests
do not prove adversarial grader integrity or sandbox security. Source capture
is after the shared Harbor verifier; replay independently checks the captured
post-verification state, not necessarily a pre-verification snapshot.
This distinction matters for candidates with side effects.

The mock qualification establishes the replay mechanism. The [separate real-candidate cohort](real-candidate-replay-observations.md) subsequently recorded both a pass and a failure, with agreement in fresh verifier processes. The actual generated source bytes were not published. Do not retrofit these claims onto previous redacted observations.

## Local replay command

From a trusted checkout on a POSIX host with a local Linux Docker daemon and
the pinned replay image already present, run:

```bash
cost-to-done replay-candidate --task allocation-repair \\
  --candidate /absolute/path/to/candidate.py --output replay.json
```

Or select a Harbor job with an explicit collected candidate artifact using
`--harbor-job` instead of `--candidate`. Exit statuses are 0 for a pass,
1 for a failed acceptance suite and 2 for unresolved execution or invalid
inputs. No inference is performed. The command does not independently
attribute an arbitrary supplied source file to a model or historical trial.

## Production opt-in and real-candidate qualification

The production runner now has an explicit candidate-capture option. It defaults
to false and does not change earlier task identities. The mock replay workflow
exercises the same opt-in path and binds collection to the exact raw result
SHA-256. The new real-replay cohort uses one allocation repair per frontier
configuration, with the same low-effort native protocol and USD 1 estimated
allowance per trial. It is deliberately distinct from the 18-trial panel.
Its paid jobs require successful completion of the original panel, successful
mock replay qualification, and the first trusted-main push. The provider
secret file is removed before fresh replay. Only redacted outcome/hash
attestations are archived; generated source is not automatically published.
Replay failure or disagreement retains the financial observation and does
not count as independently confirmed completion. This is not a provider
invoice audit or adversarial test-integrity guarantee.

## Replay exit-status interpretation

The current wrapper reserves internal container exit status 17 for a completed
negative unittest verdict. Exit 0 denotes a completed positive verdict; other
statuses, including interpreter startup errors, missing test discovery, Docker
errors and killed processes, are unresolved. The public CLI continues to return
1 for a recorded test failure and 2 for unresolved execution. Docker's logging
driver is disabled for these replay containers to avoid retaining generated
candidate-controlled output in daemon logs. The candidate and verifier still
share process state: this is not an adversarial-verifier guarantee.
Historical records preserve the wrapper digest used for their original runs;
this change does not retrospectively re-execute or alter those results.
