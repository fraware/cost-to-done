# External DeepSWE recovery accounting review

Status: proposed source audit; first CI retrieval and reconstruction pending.
No independent model executions, invoices or comparative cost ranking.

Source: [Reason Machines DeepSWE export](https://reasonmachines.com/research/reason-agent-deepswe/deepswe.json),
schema 1.1.0, publisher timestamp 14 September 2026, 07:05:00.816208 UTC,
dataset revision 0b9fabbb63b9104d678fe965e1632f2dd9eaa2ea.
The [publisher's benchmark documentation](https://reasonmachines.com/benchmarks)
describes historical grading recoveries and different execution conditions.

This audit selects all three declared historical GPT-6 Astra xhigh runs
(two Reason runs and one Codex run). It checks the 113 task-name identities
per run, reconstructs original and recovery-adjusted verdict counts, checks
reported aggregates against the individual outcome records, and compares
the declared Reason cost coverage and mean expenditure against its
published aggregate expenditure. Recovery expenditure is already included
in that total. Missing Codex cost is unavailable, never zero.

The publisher distinguishes 226 Reason assignments from 227 physical
attempts and reports no model calls in the extra setup failure or saved-patch
regrade. Those are source declarations, not independently authenticated
metering observations. The outcome records do not contain per-task cost
receipts. Shared task names do not establish matching task digests. No
statistical superiority or isolated harness effect is asserted.

Run against a local copy of the source JSON:

```bash
python -m scripts.audit_deepswe_recovery deepswe.json --output audit.json
```

The first retrieval records the source byte digest in the derived report.
Before publication, pin that observed digest and rerun the audit against
those exact bytes. The source export is not republished by this project;
only a derived report is archived. A changed source must receive a separate
review. CI does not use provider credentials.
