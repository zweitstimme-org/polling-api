"""Validate respondent counts."""

from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck

RESPONDENT_LIMITS = {
    "TELEFONISCH": (700, 4000),
    "ONLINE": (500, 6000),
    "TELEFON_ONLINE": (700, 4000),
    "PERSOENLICH": (500, 3000),
    "UNBEKANNT": (500, 6000),
}


def validate_respondents(poll: Poll) -> ValidationCheck:
    """Validate respondent count against method-specific plausible bounds."""
    method_key = poll.method_key or "UNBEKANNT"
    lower, upper = RESPONDENT_LIMITS.get(method_key, RESPONDENT_LIMITS["UNBEKANNT"])
    passed = poll.respondents is not None and lower <= poll.respondents <= upper
    return ValidationCheck(
        passed=passed,
        observed=poll.respondents,
        expected=f"{method_key}: respondents between {lower} and {upper}.",
        message=None if passed else "Respondent count is missing or outside plausible range.",
    )
