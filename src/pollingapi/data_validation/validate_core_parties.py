"""Validate expected core parties."""

from pollingapi.data_validation.config import get_validation_config
from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


def validate_core_parties(poll: Poll) -> ValidationCheck:
    """Validate that expected core parties are present for the poll."""
    expected = expected_core_parties(poll)
    present = {result.party_key for result in poll.results}
    missing = sorted(expected - present)
    return ValidationCheck(
        passed=not missing,
        observed=sorted(present),
        expected=f"Core parties present: {', '.join(sorted(expected))}.",
        message=None if not missing else "One or more expected core parties are missing.",
        affected_parties=missing,
    )


def expected_core_parties(poll: Poll) -> set[str]:
    """Return expected core party keys for the poll."""
    rules = get_validation_config().core_parties.rules
    year = _poll_year(poll)
    scope = poll.scope or "federal"
    parties: set[str] = set()

    for rule in rules:
        if rule.scope not in {"*", _scope_group(scope), scope}:
            continue
        if year is not None and rule.from_year is not None and year < rule.from_year:
            continue
        if year is not None and rule.to_year is not None and year > rule.to_year:
            continue
        parties.update(rule.parties)
    return parties


def _scope_group(scope: str) -> str:
    if scope == "federal":
        return "federal"
    return "state"


def _poll_year(poll: Poll) -> int | None:
    if poll.publish_date:
        return poll.publish_date.year
    if poll.election and poll.election.year:
        return poll.election.year
    return None
