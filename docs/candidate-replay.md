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

This is a qualification fixture only. A future separately identified paid
cohort must explicitly enable artifact capture, archive candidate bytes
under a reviewed publication policy, and bind the replay results to trial
identities and the frozen plan. Do not retrofit these claims onto previous
redacted observations.
