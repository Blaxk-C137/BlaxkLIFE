"""Server-authoritative BLX economy helpers.

BLX is a closed-loop fictional credit. Every mutation must pass through
`authorize_spend` / `credit` and is appended to an audit log. There is no
real-money purchase, cash-out or transfer in this build.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from blxverse import config

VALID_CATEGORIES = {
    "activity", "gift", "rent", "wage", "business", "purchase", "food", "travel",
    "startup", "tip", "refund", "fine", "reward", "sale",
}


class EconomyError(Exception):
    """Raised when a transaction violates economy invariants."""


def fmt_blx(amount: int | float) -> str:
    return f"{int(round(amount))} BLX"


def authorize_spend(balance: int, amount: int) -> None:
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise EconomyError("amount must be an integer number of BLX")
    if amount < 0:
        raise EconomyError("amount cannot be negative")
    if amount > config.MAX_WALLET_TXN:
        raise EconomyError("amount exceeds per-transaction limit")
    if balance < amount:
        raise EconomyError("insufficient BLX balance")


def credit(balance: int, amount: int) -> int:
    if not isinstance(amount, int) or isinstance(amount, bool):
        raise EconomyError("amount must be an integer number of BLX")
    if amount < 0:
        raise EconomyError("credit amount cannot be negative")
    if amount > config.MAX_WALLET_TXN:
        raise EconomyError("credit exceeds per-transaction limit")
    return balance + amount


def make_entry(*, minute: float, actor_id: str, amount: int, balance_after: int,
               category: str, memo: str, counterparty: str | None = None) -> dict:
    if category not in VALID_CATEGORIES:
        raise EconomyError(f"invalid ledger category: {category}")
    return {
        "id": f"txn_{int(minute)}_{abs(amount)}_{category}",
        "minute": round(minute, 1), "day": int(minute // 1440) + 1,
        "actor": actor_id, "amount": int(amount), "balance_after": int(balance_after),
        "category": category, "memo": memo[:120], "counterparty": counterparty,
    }


def audit_path() -> str:
    base = config.data_dir()
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "audit.log")


def audit(event: dict) -> None:
    """Append-only economic audit trail (no personal audio/transcripts)."""
    try:
        record = dict(event)
        record.setdefault("at", datetime.now(UTC).isoformat())
        with open(audit_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Audit must never crash gameplay; the in-memory ledger still records it.
        pass


def validate_price(price: int) -> int:
    if not isinstance(price, int) or price < 0 or price > 5000:
        raise EconomyError("invalid price")
    return price
