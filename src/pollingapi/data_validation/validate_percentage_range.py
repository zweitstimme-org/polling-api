"""Validate party percentage ranges."""

from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


def validate_percentage_range(poll: Poll) -> ValidationCheck:
    """Validate that each party percentage is between 0 and 100."""
    invalid_parties = [
        result.party_key for result in poll.results if not 0 <= result.percentage <= 100
    ]
    return ValidationCheck(
        passed=not invalid_parties and bool(poll.results),
        observed={result.party_key: result.percentage for result in poll.results},
        expected="Each party percentage must be between 0 and 100.",
        message=None
        if not invalid_parties and poll.results
        else "One or more party percentages are outside the allowed range.",
        affected_parties=invalid_parties,
    )
