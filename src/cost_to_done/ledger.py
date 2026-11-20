"""Crash-persistent, conservative monetary authorization for future inference gateways.

An admission ledger is only one component of a spending boundary. Actual
provider-side containment also requires exclusive network routing, correct
request-specific maximum-charge estimates, credential isolation, and billing
reconciliation. No claim of a hard provider billing limit follows from this
module alone.

Money is represented in integral 10^-12 USD units throughout SQLite. Floats,
implicit zero costs, negative charges, and unbounded provider expenses are not
accepted. Uncertain requests retain their full reservation until reconciled.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from .core import ReceiptError

_SCALE = 10**12
_MONEY = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_MAX_BUDGET = 100_000 * _SCALE


def _units(value: str, *, allow_zero: bool = True) -> int:
    """Convert an exact decimal USD string to 10^-12 USD integer units."""
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise ReceiptError("money must be an exact nonnegative decimal USD string (max 12 decimal places)")
    amount = Decimal(value) * _SCALE
    if not amount.is_finite() or amount != amount.to_integral_exact():
        raise ReceiptError("invalid USD amount")
    units = int(amount)
    if units > _MAX_BUDGET or (units == 0 and not allow_zero):
        raise ReceiptError("USD amount outside permitted interval")
    return units


def _usd(units: int) -> str:
    """Render exact monetary units as plain decimal USD."""
    value = format(Decimal(units) / Decimal(_SCALE), "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


@dataclass(frozen=True)
class BudgetSnapshot:
    """Spend, outstanding authorizations and remaining available credit."""

    limit: str
    settled: str
    reserved: str
    available: str
    breached: bool
    pending: int
    uncertain: int
    schedule_sha256: str | None = None

    def to_dict(self) -> dict[str, str | bool | int]:
        return vars(self).copy()


class BudgetLedger:
    """Transactional local authorization ledger for a single evaluation run.

    Call `reserve` *before* forwarding the request to a provider. On a known
    billed amount call `settle`; on an ambiguous outcome call `mark_uncertain`.
    The latter continues to consume the full reservation, preventing budget
    reuse on timed-out, cancelled or disconnected requests.
    """

    def __init__(self, path: Path, *, budget_usd: str | None = None):
        self.path = Path(path)
        if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
            raise ReceiptError("ledger path must be a regular file, not a symlink")
        if self.path.exists() and budget_usd is not None:
            # Existing files are never silently reinitialized at a new limit.
            requested = _units(budget_usd, allow_zero=False)
        elif budget_usd is not None:
            requested = _units(budget_usd, allow_zero=False)
        else:
            requested = None
        if not self.path.exists() and requested is None:
            raise ReceiptError("new budget ledger needs a positive budget_usd")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            self.path.touch(mode=0o600, exist_ok=False)
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), limit_units INTEGER NOT NULL CHECK(limit_units>0))")
            db.execute("CREATE TABLE IF NOT EXISTS rate_schedule (id INTEGER PRIMARY KEY CHECK(id=1), sha256 TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, maximum INTEGER NOT NULL CHECK(maximum >= 0),
                actual INTEGER CHECK(actual >= 0),
                state TEXT NOT NULL CHECK(state IN ('pending','uncertain','settled'))
            )""")
            existing = db.execute("SELECT limit_units FROM meta WHERE id=1").fetchone()
            if existing is None:
                if requested is None:
                    raise ReceiptError("ledger is uninitialized; budget required")
                db.execute("INSERT INTO meta VALUES(1,?)", (requested,))
            elif requested is not None and existing[0] != requested:
                raise ReceiptError("existing budget differs; refusing silent budget change")

    def bind_schedule(self, sha256: str) -> None:
        """Persist one price schedule identity before the first request.

        A ledger with existing reservations cannot be retroactively assigned a
        rate schedule. A previously assigned identity cannot change.
        """
        if not isinstance(sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ReceiptError("invalid SHA-256 price schedule identity")
        with self._transaction() as db:
            existing = db.execute("SELECT sha256 FROM rate_schedule WHERE id=1").fetchone()
            if existing is None:
                if db.execute("SELECT 1 FROM requests LIMIT 1").fetchone():
                    raise ReceiptError("cannot attach a price schedule after spending began")
                db.execute("INSERT INTO rate_schedule VALUES(1,?)", (sha256,))
            elif existing[0] != sha256:
                raise ReceiptError("price schedule differs from ledger's immutable identity")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Serialize all admission decisions, including across processes."""
        db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _summary(db: sqlite3.Connection) -> tuple[int, int, int, int, int, int]:
        limit_row = db.execute("SELECT limit_units FROM meta WHERE id=1").fetchone()
        if limit_row is None:
            raise ReceiptError("uninitialized ledger")
        limit = int(limit_row[0])
        totals = db.execute("""SELECT
              COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN state!='settled' THEN maximum ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN state='pending' THEN 1 ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN state='uncertain' THEN 1 ELSE 0 END),0),
              COALESCE(SUM(CASE WHEN state='settled' AND actual > maximum THEN 1 ELSE 0 END),0)
            FROM requests""").fetchone()
        assert totals is not None
        return (limit, *map(int, totals))

    def snapshot(self) -> BudgetSnapshot:
        """Return an exact, auditable accounting snapshot without API access."""
        with self._transaction() as db:
            limit, settled, reserved, pending, uncertain, overruns = self._summary(db)
        remaining = limit - settled - reserved
        with self._transaction() as db:
            schedule = db.execute("SELECT sha256 FROM rate_schedule WHERE id=1").fetchone()
        return BudgetSnapshot(_usd(limit), _usd(settled), _usd(reserved),
                              _usd(max(0, remaining)), remaining < 0 or overruns > 0,
                              pending, uncertain, schedule[0] if schedule else None)

    def reserve(self, request_id: str, maximum_usd: str) -> BudgetSnapshot:
        """Atomically admit a bounded request or reject it before forwarding."""
        if not isinstance(request_id, str) or not _ID.fullmatch(request_id):
            raise ReceiptError("invalid request ID")
        amount = _units(maximum_usd, allow_zero=False)
        with self._transaction() as db:
            if db.execute("SELECT 1 FROM requests WHERE id=?", (request_id,)).fetchone():
                raise ReceiptError("duplicate request ID; possible double forwarding")
            limit, settled, reserved, _, _, overruns = self._summary(db)
            if overruns:
                raise ReceiptError("budget admission denied: previous request exceeded its authorization")
            if settled + reserved + amount > limit:
                raise ReceiptError("budget admission denied: insufficient unreserved USD")
            db.execute("INSERT INTO requests(id,maximum,state) VALUES(?,?,'pending')", (request_id, amount))
        return self.snapshot()

    def mark_uncertain(self, request_id: str) -> BudgetSnapshot:
        """Retain full reservation for a timeout, stream loss or disputed bill."""
        with self._transaction() as db:
            found = db.execute("SELECT state FROM requests WHERE id=?", (request_id,)).fetchone()
            if found is None or found[0] not in ("pending", "uncertain"):
                raise ReceiptError("request is missing or already settled")
            db.execute("UPDATE requests SET state='uncertain' WHERE id=?", (request_id,))
        return self.snapshot()

    def settle(self, request_id: str, actual_usd: str) -> BudgetSnapshot:
        """Record independently established billing, including any overrun.

        Actual charges above the authorization are retained and flagged as a
        breach, not silently capped. No future request is admitted past budget.
        """
        amount = _units(actual_usd)
        with self._transaction() as db:
            found = db.execute("SELECT state FROM requests WHERE id=?", (request_id,)).fetchone()
            if found is None or found[0] not in ("pending", "uncertain"):
                raise ReceiptError("request is missing or already settled")
            db.execute("UPDATE requests SET actual=?, state='settled' WHERE id=?", (amount, request_id))
        return self.snapshot()

    def entries(self) -> list[dict[str, str | None]]:
        """Return minimal immutable accounting data without prompts or secrets."""
        with self._transaction() as db:
            rows = db.execute("SELECT id, maximum, actual, state FROM requests ORDER BY id").fetchall()
        return [{"request_id": r[0], "reserved_max_usd": _usd(r[1]),
                 "actual_usd": _usd(r[2]) if r[2] is not None else None,
                 "state": r[3]} for r in rows]
