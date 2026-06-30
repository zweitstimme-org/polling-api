"""Tests for read-only data validation."""

from __future__ import annotations

import datetime as dt
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pollingapi.data_validation.service import DataValidationService
from pollingapi.database import Base
from pollingapi.models import Poll, PollResult, PollValidation


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


def test_validation_can_be_persisted_without_changing_poll() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    poll = Poll(
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
    session.add(poll)
    session.commit()

    service = DataValidationService(session, today=dt.date(2024, 6, 30))
    report = service.run(persist=True)

    validation = session.query(PollValidation).one()
    assert report.summary.valid_polls == 1
    assert validation.poll_id == poll.id
    assert validation.valid is True
    assert validation.result_sum_check is True
    assert validation.details["public_id"] == "C00000001"
    assert session.query(Poll).one().respondents == 1200

    persisted = service.get_persisted("C00000001")
    assert persisted is not None
    assert persisted.poll_id == poll.id
    assert persisted.valid is True
