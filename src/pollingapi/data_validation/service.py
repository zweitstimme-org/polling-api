"""Validation orchestration for cleaned polling data."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session, joinedload

from pollingapi.data_validation.config import get_validation_config
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
    "qc_party_percentage_range",
    "qc_result_sum_check",
    "qc_date_consistency",
    "qc_respondents_plausible",
    "qc_core_parties_present",
    "qc_institute_result_jump",
    "qc_scope_result_jump",
)

LEGACY_CHECK_NAMES = {
    "party_percentage_range": "qc_party_percentage_range",
    "result_sum_check": "qc_result_sum_check",
    "date_consistency": "qc_date_consistency",
    "respondents_plausible": "qc_respondents_plausible",
    "core_parties_present": "qc_core_parties_present",
    "institute_result_jump": "qc_institute_result_jump",
    "scope_result_jump": "qc_scope_result_jump",
}


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
            "qc_party_percentage_range": validate_percentage_range(poll),
            "qc_result_sum_check": validate_result_sum(poll),
            "qc_date_consistency": validate_dates(poll, today=self.today),
            "qc_respondents_plausible": validate_respondents(poll),
            "qc_core_parties_present": validate_core_parties(poll),
            "qc_institute_result_jump": validate_jump(
                poll,
                previous_by_institute,
                group_value=poll.institute_key,
                group_name="institute",
            ),
            "qc_scope_result_jump": validate_jump(
                poll,
                previous_by_scope,
                group_value=poll.scope,
                group_name="scope",
            ),
        }
        valid = self._is_research_ready(checks)
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
        validation.qc_party_percentage_range = item.qc_party_percentage_range.passed
        validation.qc_result_sum_check = item.qc_result_sum_check.passed
        validation.qc_date_consistency = item.qc_date_consistency.passed
        validation.qc_respondents_plausible = item.qc_respondents_plausible.passed
        validation.qc_core_parties_present = item.qc_core_parties_present.passed
        validation.qc_institute_result_jump = item.qc_institute_result_jump.passed
        validation.qc_scope_result_jump = item.qc_scope_result_jump.passed
        validation.details = item.model_dump(mode="json")

    def _from_model(self, validation: PollValidation) -> DataValidation:
        details = dict(validation.details)
        for old_name, new_name in LEGACY_CHECK_NAMES.items():
            if old_name in details and new_name not in details:
                details[new_name] = details.pop(old_name)
        details["id"] = validation.id
        details["poll_id"] = validation.poll_id
        details["validated_at"] = validation.validated_at
        return DataValidation.model_validate(details)

    def _checks(self, item: DataValidation) -> list[ValidationCheck]:
        return [getattr(item, name) for name in CHECK_NAMES]

    def _has_warning(self, item: DataValidation) -> bool:
        return any(check.severity == "warning" and not check.passed for check in self._checks(item))

    def _is_research_ready(self, checks: dict[str, ValidationCheck]) -> bool:
        required_checks = get_validation_config().public_dataset.required_checks
        if required_checks:
            unknown = sorted(set(required_checks) - set(checks))
            if unknown:
                raise ValueError(f"Unknown public dataset required check(s): {unknown}")
            return all(checks[name].passed for name in required_checks)
        return all(check.passed for check in checks.values() if check.severity == "error")
