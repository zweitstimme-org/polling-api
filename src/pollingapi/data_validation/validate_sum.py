"""Validate that poll results sum to roughly 100 percent."""


def validate_sum(percentages: list[float], tolerance: float = 2.0) -> bool:
    """Return whether party percentages sum to 100 within tolerance."""
    total = sum(percentages)
    return 100 - tolerance <= total <= 100 + tolerance
