# Budget authorization ledger — experimental foundation

**Status:** Implemented and tested locally. A narrowly scoped, opt-in non-streaming HTTP inference gateway now calls this ledger for every supported forwarded request. Network isolation from agents and real-provider invoice reconciliation are still unverified. See [Gateway](gateway.md).

A safe work-cost benchmark needs more than an elapsed-time timeout. An agent might launch several expensive requests, a request might be billed despite a timeout, and a retry might start before an earlier charge settles. A durable reservation ledger makes these cases explicit and prevents double allocation of a locally declared budget.

## Programming interface

The provisional Python API is:

```python
from pathlib import Path
from cost_to_done.ledger import BudgetLedger

ledger = BudgetLedger(Path("runs/trial-001-budget.db"), budget_usd="1.00")
ledger.reserve("request-001", "0.30")      # reserve conservative request maximum
ledger.mark_uncertain("request-001")          # connection dropped, charge unknown
# An independent billing source eventually confirms the amount.
ledger.settle("request-001", "0.12")          # releases unused reserved amount
print(ledger.snapshot().to_dict())
```

An already created ledger is opened with `BudgetLedger(path)`; supplying a different limit is rejected. `reserve` refuses duplicate request IDs and insufficient unreserved funds. The ledger uses SQLite transactions with `BEGIN IMMEDIATE`, recording currency in integer trillionths of a US dollar, never floating-point approximations. Separate processes and threads see the same reservation state. A failed or ambiguous request continues to reserve its entire maximum until explicitly reconciled. No operation silently marks an unknown charge as zero.

If a reconciled actual charge exceeds its reservation, the overrun is retained and flagged as a breach, and later authorization is denied. The ledger records what happened, not what was authorized. It does not conceal a provider billing discrepancy.

## Scope of the claim

This is a **local admission record**, not a hard spending control. A genuine control needs all of the following properties, demonstrated through integration tests and failure injection:

1. The provider secret belongs exclusively to the trusted metering gateway; the evaluated agent has no direct provider credentials or alternate egress route.
2. Every supported inference request is parsed and has a trustworthy, conservative maximum possible charge calculated before forwarding. Unknown tariffs, uncapped generation and unsupported modalities are denied.
3. Reservations precede network transmission and are reconciled against provider-reported usage or invoices. Streaming, failures, disconnections, hidden tokens, token caching, and retries have explicit charge policies.
4. Persistent ledgers and process restarts preserve pending authorizations. All budget breaches, overcharges and missing usage remain in the evidence.
5. Provider-side account spending controls remain an independent backstop; absent their guarantees, no absolute upper bound on charged expenditure is claimed.

The experimental gateway implements one fixed OpenAI Chat Completions protocol and uses an operator-declared price schedule. It does **not** implement a provider network firewall, exact tokenizer proof, provider invoice reconciliation, or a cryptographic audit log. The ledger binds its first assigned price-schedule SHA-256 digest and refuses subsequent replacements. Do not wire untrusted models directly to payment credentials on the strength of this component.

## Test evidence

The unit tests cover exact arithmetic, preservation of uncertain charges, duplicate request rejection, concurrent reservation races, persistence across reopening, attempts to change the budget, overrun detection, and fail-closed behavior. Run them locally with:

```bash
python -m unittest tests.test_ledger -v
```

The suite uses no model credentials and incurs no inference expenditure.
