"""Validate result jumps against previous comparable polls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pollingapi.data_validation.config import get_validation_config
from pollingapi.models import Poll
from pollingapi.schemas import ValidationCheck


@dataclass(frozen=True)
class PreviousResult:
    """Previous comparable party result."""

    poll_id: int
    public_id: str | None
    percentage: float


def validate_jump(
    poll: Poll,
    previous_results: dict[tuple[str, str], PreviousResult],
    *,
    group_value: str | None,
    group_name: str,
) -> ValidationCheck:
    """Validate jumps against previous results in the same group."""
    threshold = get_validation_config().jump_threshold
    if not group_value:
        return ValidationCheck(
            passed=True,
            severity="warning",
            expected=f"Previous poll with same {group_name}.",
            message=f"No {group_name} value available for jump check.",
        )

    jumps: list[dict[str, Any]] = []
    for result in poll.results:
        previous = previous_results.get((group_value, result.party_key))
        if not previous:
            continue
        jump = result.percentage - previous.percentage
        if abs(jump) > threshold:
            jumps.append(
                {
                    "party_key": result.party_key,
                    "jump": round(jump, 2),
                    "current": result.percentage,
                    "previous": previous.percentage,
                    "previous_poll_id": previous.poll_id,
                    "previous_public_id": previous.public_id,
                }
            )

    return ValidationCheck(
        passed=not jumps,
        severity="warning",
        observed=jumps,
        expected=f"No party jump greater than {threshold:.0f} percentage points.",
        message=None if not jumps else f"Large party result jump within same {group_name}.",
        affected_parties=[jump["party_key"] for jump in jumps],
    )


def remember_poll_results(
    poll: Poll,
    previous_by_institute: dict[tuple[str, str], PreviousResult],
    previous_by_scope: dict[tuple[str, str], PreviousResult],
) -> None:
    """Remember this poll as the previous result for future jump checks."""
    for result in poll.results:
        previous = PreviousResult(
            poll_id=poll.id,
            public_id=poll.public_id,
            percentage=result.percentage,
        )
        if poll.institute_key:
            previous_by_institute[(poll.institute_key, result.party_key)] = previous
        if poll.scope:
            previous_by_scope[(poll.scope, result.party_key)] = previous
