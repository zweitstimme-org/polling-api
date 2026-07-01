"""Validate that poll results sum to roughly 100 percent."""

from pollingapi.data_validation.config import get_validation_config
from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


def validate_sum(percentages: list[float], tolerance: float = 2.0) -> bool:
    """Return whether party percentages sum to 100 within tolerance."""
    total = sum(percentages)
    return 100 - tolerance <= total <= 100 + tolerance


def validate_result_sum(poll: Poll, tolerance: float | None = None) -> ValidationCheck:
    """Validate that party percentages sum to 100 within tolerance."""
    tolerance = tolerance if tolerance is not None else get_validation_config().sum_tolerance
    percentages = [result.percentage for result in poll.results]
    total = sum(percentages)
    passed = bool(percentages) and validate_sum(percentages, tolerance=tolerance)
    return ValidationCheck(
        passed=passed,
        observed=round(total, 2),
        expected=f"Sum between {100 - tolerance:.0f} and {100 + tolerance:.0f}.",
        message=None if passed else "Party results do not sum to 100 within tolerance.",
    )
