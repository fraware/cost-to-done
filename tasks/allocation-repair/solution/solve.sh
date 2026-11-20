#!/usr/bin/env bash
set -euo pipefail
# Only the oracle agent receives this file; agent workspaces exclude solution/.
root="${APP_ROOT:-/app}"
cat > "$root/allocate.py" <<'PY'
"""Exact proportional integer-cent allocation."""


def allocate_cents(total_cents: int, weights: list[int]) -> list[int]:
    """Allocate cents by largest remainder with stable, index-first ties.

    Input validation uses exact types to exclude bool, a subclass of int.
    The algorithm never converts amounts or ratios to floating point.
    """
    if type(total_cents) is not int or total_cents < 0:
        raise ValueError("total_cents must be a nonnegative integer")
    if not isinstance(weights, list) or not weights:
        raise ValueError("weights must be a nonempty list")
    if any(type(w) is not int or w < 0 for w in weights):
        raise ValueError("weights must be nonnegative integers")
    denominator = sum(weights)
    if denominator == 0:
        raise ValueError("at least one weight must be positive")

    shares = []
    remainders = []
    for weight in weights:
        share, remainder = divmod(total_cents * weight, denominator)
        shares.append(share)
        remainders.append(remainder)

    extra = total_cents - sum(shares)
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:extra]:
        shares[i] += 1
    return shares
PY
