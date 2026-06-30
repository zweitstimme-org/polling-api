"""Validation orchestration for cleaned polling data."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session, joinedload

from pollingapi.data_validation.validate_core_parties import validate_core_parties
from pollingapi.data_validation.validate_dates import validate_dates
from pollingapi.data_validation.validate_jumps import (
    PreviousResult,
    remember_poll_results,
    validate_jump,
)
from pollingapi.data_validation.validate_percentage_range import validate_percentage_range
from pollingapi.data_validation.validate_respondents import validate_respondents
from pollingapi.data_validation.validate_sum import validate_result_sum
from pollingapi.models import Poll, PollResult, PollValidation
from pollingapi.schemas import (
    DataValidation,
    DataValidationResponse,
    DataValidationSummary,
    ValidationCheck,
)

CHECK_NAMES = (
    "party_percentage_range",
    "result_sum_check",
    "date_consistency",
    "respondents_plausible",
    "core_parties_present",
    "institute_result_jump",
    "scope_result_jump",
)


class DataValidationService:
    """Validate cleaned polls and optionally persist validation rows."""

    def __init__(self, db: Session, today: dt.date | None = None):
        """Initialize the validation service."""
        self.db = db
        self.today = today or dt.date.today()

    def run(self, limit: int | None = None, persist: bool = False) -> DataValidationResponse:
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
            remember_poll_results(poll, previous_by_institute, previous_by_scope)
            if persist:
                self._upsert_validation(item)

        if persist:
            self.db.commit()

        valid_polls = sum(item.valid for item in items)
        warning_polls = sum(self._has_warning(item) for item in items)
        summary = DataValidationSummary(
            total_polls=len(items),
            valid_polls=valid_polls,
            invalid_polls=len(items) - valid_polls,
            warning_polls=warning_polls,
        )
        return DataValidationResponse(summary=summary, items=items)

    def get_persisted(self, poll_identifier: str) -> DataValidation | None:
        """Return a persisted validation report by poll id or public id."""
        query = self.db.query(Poll).options(joinedload(Poll.validation))
        if poll_identifier.upper().startswith("C"):
            query = query.filter(Poll.public_id == poll_identifier.upper())
        elif poll_identifier.isdigit():
            query = query.filter(Poll.id == int(poll_identifier))
        else:
            return None

        poll = query.first()
        if not poll or not poll.validation:
            return None
        return self._from_model(poll.validation)

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
            "party_percentage_range": validate_percentage_range(poll),
            "result_sum_check": validate_result_sum(poll),
            "date_consistency": validate_dates(poll, today=self.today),
            "respondents_plausible": validate_respondents(poll),
            "core_parties_present": validate_core_parties(poll),
            "institute_result_jump": validate_jump(
                poll,
                previous_by_institute,
                group_value=poll.institute_key,
                group_name="institute",
            ),
            "scope_result_jump": validate_jump(
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

    def _upsert_validation(self, item: DataValidation) -> None:
        validation = (
            self.db.query(PollValidation).filter(PollValidation.poll_id == item.poll_id).first()
        )
        if validation is None:
            validation = PollValidation(poll_id=item.poll_id, validated_at=dt.datetime.now())
            self.db.add(validation)

        checks = self._checks(item)
        validation.valid = item.valid
        validation.validated_at = dt.datetime.now()
        validation.error_count = sum(
            not check.passed for check in checks if check.severity == "error"
        )
        validation.warning_count = sum(
            not check.passed for check in checks if check.severity == "warning"
        )
        validation.party_percentage_range = item.party_percentage_range.passed
        validation.result_sum_check = item.result_sum_check.passed
        validation.date_consistency = item.date_consistency.passed
        validation.respondents_plausible = item.respondents_plausible.passed
        validation.core_parties_present = item.core_parties_present.passed
        validation.institute_result_jump = item.institute_result_jump.passed
        validation.scope_result_jump = item.scope_result_jump.passed
        validation.details = item.model_dump(mode="json")

    def _from_model(self, validation: PollValidation) -> DataValidation:
        details = dict(validation.details)
        details["id"] = validation.id
        details["poll_id"] = validation.poll_id
        details["validated_at"] = validation.validated_at
        return DataValidation.model_validate(details)

    def _checks(self, item: DataValidation) -> list[ValidationCheck]:
        return [getattr(item, name) for name in CHECK_NAMES]

    def _has_warning(self, item: DataValidation) -> bool:
        return any(check.severity == "warning" and not check.passed for check in self._checks(item))
