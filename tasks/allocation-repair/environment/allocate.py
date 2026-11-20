"""Integer-cent proportional allocation (intentionally defective starter)."""


def allocate_cents(total_cents: int, weights: list[int]) -> list[int]:
    """Allocate total cents by weight, retaining the caller's index order."""
    if not weights:
        return []
    total_weight = sum(weights)
    return [round(total_cents * weight / total_weight) for weight in weights]
