"""Validate expected core parties."""

import datetime as dt
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field

from pollingapi.data_validation.config import get_validation_config
from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


@dataclass(frozen=True)
class CorePartyPresenceContext:
    """Nearby poll counts by poll and party."""

    counts: dict[int, dict[str, tuple[int, int]]] = field(default_factory=dict)


def validate_core_parties(
    poll: Poll,
    comparison_polls: list[Poll] | None = None,
    presence_context: CorePartyPresenceContext | None = None,
) -> ValidationCheck:
    """Validate that contextually expected core parties are present for the poll."""
    expected = expected_core_parties(poll)
    present = {result.party_key for result in poll.results}
    missing = expected - present
    blocking_missing = _blocking_missing_parties(
        poll,
        missing,
        comparison_polls=comparison_polls,
        presence_context=presence_context,
    )

    if missing and not blocking_missing:
        severity = "warning"
        message = "One or more monitored core parties are missing, but nearby polls do not make this a blocking issue."
    elif blocking_missing:
        severity = "error"
        message = "One or more contextually expected core parties are missing."
    else:
        severity = "error"
        message = None

    return ValidationCheck(
        passed=not blocking_missing,
        severity=severity,
        observed=sorted(present),
        expected=f"Contextual core parties present: {', '.join(sorted(expected))}.",
        message=message,
        affected_parties=sorted(blocking_missing or missing),
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


def build_core_party_presence_context(polls: list[Poll]) -> CorePartyPresenceContext:
    """Build reusable nearby poll party counts."""
    config = get_validation_config().core_parties.presence_policy
    window = dt.timedelta(days=config.window_days)
    monitored_parties = set().union(*(expected_core_parties(poll) for poll in polls))
    counts: dict[int, dict[str, tuple[int, int]]] = {}

    for scope_polls in _polls_by_scope(polls).values():
        dated = sorted(
            [poll for poll in scope_polls if poll.publish_date is not None],
            key=lambda poll: (poll.publish_date, poll.id or 0),
        )
        dates = [poll.publish_date for poll in dated if poll.publish_date is not None]
        party_prefix = {party: _prefix_counts(dated, party) for party in monitored_parties}

        for poll in dated:
            left = bisect_left(dates, poll.publish_date - window)
            right = bisect_right(dates, poll.publish_date + window)
            total = right - left - 1
            counts[id(poll)] = {
                party: (
                    total,
                    party_prefix[party][right]
                    - party_prefix[party][left]
                    - int(_has_party(poll, party)),
                )
                for party in monitored_parties
            }

        undated = [poll for poll in scope_polls if poll.publish_date is None]
        if undated:
            total = len(scope_polls) - 1
            for poll in undated:
                counts[id(poll)] = {
                    party: (
                        total,
                        sum(_has_party(candidate, party) for candidate in scope_polls)
                        - int(_has_party(poll, party)),
                    )
                    for party in monitored_parties
                }

    return CorePartyPresenceContext(counts=counts)


def _blocking_missing_parties(
    poll: Poll,
    missing: set[str],
    *,
    comparison_polls: list[Poll] | None,
    presence_context: CorePartyPresenceContext | None,
) -> set[str]:
    config = get_validation_config().core_parties.presence_policy
    if not missing or not config.enabled:
        return missing

    if presence_context is None and comparison_polls is not None:
        presence_context = build_core_party_presence_context(comparison_polls)
    if presence_context is None:
        return missing

    counts = presence_context.counts.get(id(poll), {})
    blocking = set()
    for party in missing:
        comparison_count, present_count = counts.get(party, (0, 0))
        if comparison_count < config.min_comparison_polls:
            continue
        if present_count / comparison_count >= config.min_presence_share:
            blocking.add(party)
    return blocking


def _polls_by_scope(polls: list[Poll]) -> dict[str | None, list[Poll]]:
    grouped: dict[str | None, list[Poll]] = {}
    for poll in polls:
        grouped.setdefault(poll.scope, []).append(poll)
    return grouped


def _prefix_counts(polls: list[Poll], party_key: str) -> list[int]:
    counts = [0]
    for poll in polls:
        counts.append(counts[-1] + int(_has_party(poll, party_key)))
    return counts


def _has_party(poll: Poll, party_key: str) -> bool:
    return any(result.party_key == party_key for result in poll.results)
