"""Read-only validation for cleaned polling data."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, joinedload

from pollingapi.data_validation.validate_sum import validate_sum
from pollingapi.models import Poll, PollResult
from pollingapi.schemas import (
    DataValidation,
    DataValidationResponse,
    DataValidationSummary,
    ValidationCheck,
)

SUM_TOLERANCE = 2.0
JUMP_THRESHOLD = 4.0

RESPONDENT_LIMITS = {
    "TELEFONISCH": (700, 4000),
    "ONLINE": (500, 6000),
    "TELEFON_ONLINE": (700, 4000),
    "PERSOENLICH": (500, 3000),
    "UNBEKANNT": (500, 6000),
}


@dataclass(frozen=True)
class PreviousResult:
    """Previous comparable party result."""

    poll_id: int
    public_id: str | None
    percentage: float


class DataValidationService:
    """Validate cleaned polls without writing to the database."""

    def __init__(self, db: Session, today: dt.date | None = None):
        """Initialize the validation service."""
        self.db = db
        self.today = today or dt.date.today()

    def run(self, limit: int | None = None) -> DataValidationResponse:
        """Validate cleaned polls and return a report."""
        polls = self._load_polls(limit=limit)
        previous_by_institute: dict[tuple[str, str], PreviousResult] = {}
        previous_by_scope: dict[tuple[str, str], PreviousResult] = {}
        items: list[DataValidation] = []

        for poll in polls:
            item = self._validate_poll(
                poll,
                previous_by_institute=previous_by_institute,
                previous_by_scope=previous_by_scope,
            )
            items.append(item)
            self._remember_poll_results(poll, previous_by_institute, previous_by_scope)

        valid_polls = sum(item.valid for item in items)
        warning_polls = sum(self._has_warning(item) for item in items)
        summary = DataValidationSummary(
            total_polls=len(items),
            valid_polls=valid_polls,
            invalid_polls=len(items) - valid_polls,
            warning_polls=warning_polls,
        )
        return DataValidationResponse(summary=summary, items=items)

    def _load_polls(self, limit: int | None) -> list[Poll]:
        query = (
            self.db.query(Poll)
            .options(
                joinedload(Poll.election),
                joinedload(Poll.method),
                joinedload(Poll.results).joinedload(PollResult.party),
            )
            .order_by(Poll.publish_date.asc(), Poll.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def _validate_poll(
        self,
        poll: Poll,
        *,
        previous_by_institute: dict[tuple[str, str], PreviousResult],
        previous_by_scope: dict[tuple[str, str], PreviousResult],
    ) -> DataValidation:
        checks = {
            "party_percentage_range": self._validate_percentage_range(poll),
            "result_sum_check": self._validate_result_sum(poll),
            "date_consistency": self._validate_dates(poll),
            "respondents_plausible": self._validate_respondents(poll),
            "core_parties_present": self._validate_core_parties(poll),
            "institute_result_jump": self._validate_jump(
                poll,
                previous_by_institute,
                group_value=poll.institute_key,
                group_name="institute",
            ),
            "scope_result_jump": self._validate_jump(
                poll,
                previous_by_scope,
                group_value=poll.scope,
                group_name="scope",
            ),
        }
        valid = all(check.passed for check in checks.values() if check.severity == "error")
        return DataValidation(
            poll_id=poll.id,
            public_id=poll.public_id,
            valid=valid,
            **checks,
        )

    def _validate_percentage_range(self, poll: Poll) -> ValidationCheck:
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

    def _validate_result_sum(self, poll: Poll) -> ValidationCheck:
        percentages = [result.percentage for result in poll.results]
        total = sum(percentages)
        passed = bool(percentages) and validate_sum(percentages, tolerance=SUM_TOLERANCE)
        return ValidationCheck(
            passed=passed,
            observed=round(total, 2),
            expected=f"Sum between {100 - SUM_TOLERANCE:.0f} and {100 + SUM_TOLERANCE:.0f}.",
            message=None if passed else "Party results do not sum to 100 within tolerance.",
        )

    def _validate_dates(self, poll: Poll) -> ValidationCheck:
        dates = [poll.survey_date_start, poll.survey_date_end, poll.publish_date]
        if any(value is None for value in dates):
            return ValidationCheck(
                passed=False,
                observed=self._date_observation(poll),
                expected="survey_date_start <= survey_date_end <= publish_date; no future dates.",
                message="One or more required dates are missing.",
            )

        start = poll.survey_date_start
        end = poll.survey_date_end
        publish = poll.publish_date
        passed = start <= end <= publish and all(value <= self.today for value in dates if value)
        return ValidationCheck(
            passed=passed,
            observed=self._date_observation(poll),
            expected="survey_date_start <= survey_date_end <= publish_date; no future dates.",
            message=None if passed else "Poll dates are inconsistent or in the future.",
        )

    def _validate_respondents(self, poll: Poll) -> ValidationCheck:
        method_key = poll.method_key or "UNBEKANNT"
        lower, upper = RESPONDENT_LIMITS.get(method_key, RESPONDENT_LIMITS["UNBEKANNT"])
        passed = poll.respondents is not None and lower <= poll.respondents <= upper
        return ValidationCheck(
            passed=passed,
            observed=poll.respondents,
            expected=f"{method_key}: respondents between {lower} and {upper}.",
            message=None if passed else "Respondent count is missing or outside plausible range.",
        )

    def _validate_core_parties(self, poll: Poll) -> ValidationCheck:
        expected = self._expected_core_parties(poll)
        present = {result.party_key for result in poll.results}
        missing = sorted(expected - present)
        return ValidationCheck(
            passed=not missing,
            observed=sorted(present),
            expected=f"Core parties present: {', '.join(sorted(expected))}.",
            message=None if not missing else "One or more expected core parties are missing.",
            affected_parties=missing,
        )

    def _validate_jump(
        self,
        poll: Poll,
        previous_results: dict[tuple[str, str], PreviousResult],
        *,
        group_value: str | None,
        group_name: str,
    ) -> ValidationCheck:
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
            if abs(jump) > JUMP_THRESHOLD:
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
            expected=f"No party jump greater than {JUMP_THRESHOLD:.0f} percentage points.",
            message=None if not jumps else f"Large party result jump within same {group_name}.",
            affected_parties=[jump["party_key"] for jump in jumps],
        )

    def _expected_core_parties(self, poll: Poll) -> set[str]:
        year = self._poll_year(poll)
        parties = {"SPD"}

        if poll.scope == "by":
            parties.add("CSU")
        elif poll.scope and poll.scope != "federal":
            parties.add("CDU")
        else:
            parties.add("CDU_CSU")

        if year is None or year <= 2021:
            parties.add("FDP")
        if year is None or year >= 1990:
            parties.add("GRUENE")
        if year is None or year >= 2014:
            parties.add("AFD")
        return parties

    def _poll_year(self, poll: Poll) -> int | None:
        if poll.publish_date:
            return poll.publish_date.year
        if poll.election and poll.election.year:
            return poll.election.year
        return None

    def _remember_poll_results(
        self,
        poll: Poll,
        previous_by_institute: dict[tuple[str, str], PreviousResult],
        previous_by_scope: dict[tuple[str, str], PreviousResult],
    ) -> None:
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

    def _date_observation(self, poll: Poll) -> dict[str, str | None]:
        return {
            "survey_date_start": poll.survey_date_start.isoformat()
            if poll.survey_date_start
            else None,
            "survey_date_end": poll.survey_date_end.isoformat() if poll.survey_date_end else None,
            "publish_date": poll.publish_date.isoformat() if poll.publish_date else None,
        }

    def _has_warning(self, item: DataValidation) -> bool:
        checks = [
            item.party_percentage_range,
            item.result_sum_check,
            item.date_consistency,
            item.respondents_plausible,
            item.core_parties_present,
            item.institute_result_jump,
            item.scope_result_jump,
        ]
        return any(check.severity == "warning" and not check.passed for check in checks)
