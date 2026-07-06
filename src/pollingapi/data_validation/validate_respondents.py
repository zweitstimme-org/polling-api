"""Validate respondent counts."""

from pollingapi.data_validation.config import get_validation_config
from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


def validate_respondents(poll: Poll) -> ValidationCheck:
    """Validate respondent count against method-specific plausible bounds."""
    config = get_validation_config()
    method_key = poll.method_key or "UNBEKANNT"
    lower, upper = config.respondent_limits.get(method_key, config.respondent_default)
    passed = poll.respondents is not None and lower <= poll.respondents <= upper
    return ValidationCheck(
        passed=passed,
        observed=poll.respondents,
        expected=f"{method_key}: respondents between {lower} and {upper}.",
        message=None if passed else "Respondent count is missing or outside plausible range.",
    )
