# Package a task from your repository

The first user-repository adapter is deliberately limited to standard-library
Python tasks with explicit committed files. It reads local Git objects, not
uncommitted working-tree files, and generates a Harbor task with a pinned
Python base image. It does not invoke a model, install dependencies, or run
repository code during preparation.

## Prepare a task

From a local trusted repository, select the precise source and acceptance-test
files. Write a separate task instruction, e.g. `repair.md`.

```bash
cost-to-done prepare-repo-task \
  --repository ./my-repo --revision HEAD --name repair-addition \
  --source app/calc.py --test acceptance/test_calc.py \
  --instruction repair.md --output ./repair-task
```

The output directory must not already exist, and its parent must exist.
Source paths remain relative to `/app`. Test modules have unique
`test_*.py` basenames and use Python's standard-library unittest. Tests
are outside the Docker image build context; Harbor supplies them at grading.
The task records its exact commit, blob identities, staged file hashes,
executable bits and pinned runtime. A fresh task is unqualified by design.
Review selected files and the instructions for secrets and license obligations;
path filtering is not a secret detector. Only committed regular files are
accepted, not symlinks, submodules, hidden paths, or Git LFS pointers.
Limits: 100 selected files, 1 MB per file, 10 MB aggregate.

## Qualify it without inference

Install the pinned Harbor runtime in Python 3.12 and use a local Docker
daemon on a trusted host:

```bash
python -m pip install 'harbor==0.27.0'
harbor run --path ./repair-task --agent nop --job-name starter \
  --jobs-dir ./qualification --n-concurrent 1 --n-attempts 1
cost-to-done inspect-harbor ./qualification/starter
```

A useful repair task must fail its intended acceptance criteria on the starter
and pass on an independently known correct reference. Prepare a separate
task from the reference commit with the same tests and run its nop control.
Compare verifier semantics and file identities; these two qualification
controls deliberately use different source commits and must not be treated
as matched model runs.

This command packages trusted local Python files only. It does not prove
that tests are secret, resistant to an adversarial candidate, or executed
under the qualified credential-isolated live-runner topology. The live
metered gateway currently accepts bundled tasks exclusively. Do not pass
arbitrary downloaded repositories or unreviewed task code to a privileged
runner. Paid arbitrary-repository execution remains a separate milestone.

For existing matched Harbor model jobs, use `cost-to-done compare-harbor`
to obtain offline descriptive comparisons. Available agent-reported costs
are estimates, not invoices.
