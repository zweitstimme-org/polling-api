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
    config = get_validation_config().core_parties
    year = _poll_year(poll)
    parties = {"SPD"}

    if poll.scope == "by":
        parties.add("CSU")
    elif poll.scope and poll.scope != "federal":
        parties.add("CDU")
    else:
        parties.add("CDU_CSU")

    if year is None or year <= config.fdp_until_year:
        parties.add("FDP")
    if year is None or year >= config.green_from_year:
        parties.add("GRUENE")
    if year is None or year >= config.afd_from_year:
        parties.add("AFD")
    return parties


def _poll_year(poll: Poll) -> int | None:
    if poll.publish_date:
        return poll.publish_date.year
    if poll.election and poll.election.year:
        return poll.election.year
    return None
