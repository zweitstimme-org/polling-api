"""Aggregate reports for persisted validation results."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pollingapi.data_validation.config import get_validation_config
from pollingapi.data_validation.service import CHECK_NAMES
from pollingapi.models import PollValidation
from pollingapi.schemas import (
    ValidationCheckSummary,
    ValidationFailureSummary,
    ValidationReport,
)


class ValidationReportService:
    """Build aggregate reports from persisted validation rows."""

    def __init__(self, db: Session):
        """Initialize the report service."""
        self.db = db
        self.reporting_config = get_validation_config().reporting

    def build_report(self, top_n: int = 5) -> ValidationReport:
        """Build an aggregate validation quality report."""
        rows = self._load_rows()
        total = len(rows)
        valid_polls = sum(row.valid for row in rows)
        warning_polls = sum(row.warning_count > 0 for row in rows)
        invalid_polls = total - valid_polls

        checks = [self._summarize_check(rows, check_name) for check_name in CHECK_NAMES]
        failures = [
            ValidationFailureSummary(check=check.check, failed=check.failed)
            for check in sorted(checks, key=lambda item: item.failed, reverse=True)
            if check.failed > 0
        ][:top_n]

        valid_share = _share(valid_polls, total)
        invalid_share = _share(invalid_polls, total)
        warning_share = _share(warning_polls, total)

        return ValidationReport(
            status=self._status(total, valid_share, invalid_share, warning_share),
            generated_at=dt.datetime.now(dt.UTC),
            total_polls=total,
            valid_polls=valid_polls,
            invalid_polls=invalid_polls,
            warning_polls=warning_polls,
            valid_share=valid_share,
            invalid_share=invalid_share,
            warning_share=warning_share,
            latest_validated_at=self._latest_validated_at(),
            checks=checks,
            top_failure_checks=failures,
        )

    def health_check(self) -> dict:
        """Return compact validation health payload."""
        report = self.build_report(top_n=3)
        return {
            "status": report.status,
            "total_polls": report.total_polls,
            "valid_share": report.valid_share,
            "invalid_share": report.invalid_share,
            "warning_share": report.warning_share,
            "latest_validated_at": report.latest_validated_at,
            "top_failure_checks": [
                item.model_dump(mode="json") for item in report.top_failure_checks
            ],
        }

    def _summarize_check(
        self,
        rows: list[PollValidation],
        check_name: str,
    ) -> ValidationCheckSummary:
        passed = sum(bool(getattr(row, check_name)) for row in rows)
        failed = len(rows) - passed
        return ValidationCheckSummary(
            check=check_name,
            passed=passed,
            failed=failed,
            pass_share=_share(passed, len(rows)),
        )

    def _load_rows(self) -> list[PollValidation]:
        try:
            return self.db.query(PollValidation).all()
        except SQLAlchemyError:
            self.db.rollback()
            return []

    def _latest_validated_at(self) -> dt.datetime | None:
        try:
            return self.db.query(func.max(PollValidation.validated_at)).scalar()
        except SQLAlchemyError:
            self.db.rollback()
            return None

    def _status(
        self,
        total: int,
        valid_share: float,
        invalid_share: float,
        warning_share: float,
    ) -> str:
        if total == 0:
            return "warn"
        if invalid_share > self.reporting_config.max_invalid_share:
            return "fail"
        if (
            valid_share < self.reporting_config.min_valid_share
            or warning_share > self.reporting_config.max_warning_share
        ):
            return "warn"
        return "pass"


def _share(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)
