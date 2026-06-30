"""Tests for read-only data validation."""

from __future__ import annotations

import datetime as dt
from typing import cast

from sqlalchemy.orm import Session

from pollingapi.data_validation.service import DataValidationService
from pollingapi.models import Poll, PollResult


def test_validation_accepts_plausible_poll() -> None:
    poll = Poll(
        id=1,
        public_id="C00000001",
        publish_date=dt.date(2024, 6, 1),
        survey_date_start=dt.date(2024, 5, 25),
        survey_date_end=dt.date(2024, 5, 30),
        respondents=1200,
        method_key="ONLINE",
        scope="federal",
        institute_key="FORSA",
        results=[
            PollResult(party_key="CDU_CSU", percentage=30),
            PollResult(party_key="SPD", percentage=20),
            PollResult(party_key="GRUENE", percentage=15),
            PollResult(party_key="FDP", percentage=5),
            PollResult(party_key="AFD", percentage=15),
            PollResult(party_key="SONSTIGE", percentage=15),
        ],
    )
    service = DataValidationService(cast(Session, None), today=dt.date(2024, 6, 30))

    result = service._validate_poll(
        poll,
        previous_by_institute={},
        previous_by_scope={},
    )

    assert result.valid is True
    assert result.result_sum_check.passed is True
    assert result.institute_result_jump.severity == "warning"


def test_validation_marks_sum_failure_invalid() -> None:
    poll = Poll(
        id=1,
        public_id="C00000001",
        publish_date=dt.date(2024, 6, 1),
        survey_date_start=dt.date(2024, 5, 25),
        survey_date_end=dt.date(2024, 5, 30),
        respondents=1200,
        method_key="ONLINE",
        scope="federal",
        institute_key="FORSA",
        results=[
            PollResult(party_key="CDU_CSU", percentage=30),
            PollResult(party_key="SPD", percentage=20),
            PollResult(party_key="GRUENE", percentage=15),
            PollResult(party_key="FDP", percentage=5),
            PollResult(party_key="AFD", percentage=15),
        ],
    )
    service = DataValidationService(cast(Session, None), today=dt.date(2024, 6, 30))

    result = service._validate_poll(
        poll,
        previous_by_institute={},
        previous_by_scope={},
    )

    assert result.valid is False
    assert result.result_sum_check.passed is False
    assert result.result_sum_check.observed == 85
