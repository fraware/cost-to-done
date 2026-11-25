# External DeepSWE recovery accounting review

Status: initial [CI retrieval and reconstruction](https://github.com/fraware/cost-to-done/actions/runs/45616094378) passed. Exact-source digest now pinned; second CI verification pending.
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

The auditor pins the SHA-256 observed in the successful initial retrieval:

`8128f434c608473a8987bc9d5e02ff578fcac4d6f7c611e8f4436740330f355c`

The audit rejects any different source bytes. The source export is not republished by this project;
only a derived report is archived. A changed source must receive a separate
review. CI does not use provider credentials.

## Observed publisher accounting (first successful reconstruction)

| Configuration | Assigned slots | Original pass / fail / ungraded | Final pass / fail / ungraded | Reported model spend |
| --- | ---: | ---: | ---: | ---: |
| Reason / GPT-6 Astra xhigh | 226 | 164 / 60 / 2 | 165 / 61 / 0 | $1,203.289086 |
| Codex / GPT-6 Astra xhigh | 113 | 80 / 33 / 0 | 80 / 33 / 0 | Unavailable |

Reason reports 226 cost records and zero missing records, but the audit
does not independently reconcile individual charges. Its reported model
spend divided by final passes is $7.2926611272727... per final pass
(displayed as $7.29). Recovery spending of about $5.10 is already included.
The two recovered slots produce one additional pass and one additional
failure; the audit does not infer a causal effect of retries. No comparable
Codex expenditure is published in this export, so no cost comparison is
available. The two Reason repetitions and single Codex repetition are not
a balanced experimental design.
