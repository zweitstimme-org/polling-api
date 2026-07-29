"""Tests for read-only data validation."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pollingapi.data_validation.config import get_validation_config
from pollingapi.data_validation.report import ValidationReportService
from pollingapi.data_validation.service import DataValidationService
from pollingapi.data_validation.validate_core_parties import validate_core_parties
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
    assert result.qc_result_sum_check.passed is True
    assert result.qc_institute_result_jump.severity == "warning"


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
    assert result.qc_result_sum_check.passed is False
    assert result.qc_result_sum_check.observed == 85


def test_validation_required_checks_control_research_ready_status(monkeypatch) -> None:
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
            PollResult(party_key="CDU_CSU", percentage=40),
            PollResult(party_key="SPD", percentage=30),
            PollResult(party_key="SONSTIGE", percentage=30),
        ],
    )
    monkeypatch.setattr(
        "pollingapi.data_validation.service.get_validation_config",
        lambda: SimpleNamespace(
            public_dataset=SimpleNamespace(
                required_checks=(
                    "qc_party_percentage_range",
                    "qc_result_sum_check",
                    "qc_date_consistency",
                    "qc_respondents_plausible",
                )
            )
        ),
    )
    service = DataValidationService(cast(Session, None), today=dt.date(2024, 6, 30))

    result = service._validate_poll(
        poll,
        previous_by_institute={},
        previous_by_scope={},
    )

    assert result.valid is True
    assert result.qc_core_parties_present.passed is False


def test_contextual_core_party_presence_blocks_one_off_dropout(monkeypatch) -> None:
    monkeypatch.setattr(
        "pollingapi.data_validation.validate_core_parties.get_validation_config",
        lambda: SimpleNamespace(
            core_parties=SimpleNamespace(
                rules=(
                    SimpleNamespace(scope="bb", parties=("CDU",), from_year=None, to_year=None),
                ),
                presence_policy=SimpleNamespace(
                    enabled=True,
                    min_comparison_polls=5,
                    window_days=365,
                    min_presence_share=0.8,
                ),
            )
        ),
    )
    poll = _poll_with_results(1, dt.date(2024, 6, 1), "bb", ["SPD"])
    comparison_polls = [
        _poll_with_results(index, dt.date(2024, 5, index), "bb", ["CDU", "SPD"])
        for index in range(2, 7)
    ]

    result = validate_core_parties(poll, comparison_polls=[poll, *comparison_polls])

    assert result.passed is False
    assert result.severity == "error"
    assert result.affected_parties == ["CDU"]


def test_contextual_core_party_presence_allows_consistent_absence(monkeypatch) -> None:
    monkeypatch.setattr(
        "pollingapi.data_validation.validate_core_parties.get_validation_config",
        lambda: SimpleNamespace(
            core_parties=SimpleNamespace(
                rules=(
                    SimpleNamespace(scope="bb", parties=("FDP",), from_year=None, to_year=None),
                ),
                presence_policy=SimpleNamespace(
                    enabled=True,
                    min_comparison_polls=5,
                    window_days=365,
                    min_presence_share=0.8,
                ),
            )
        ),
    )
    poll = _poll_with_results(1, dt.date(2024, 6, 1), "bb", ["SPD"])
    comparison_polls = [
        _poll_with_results(index, dt.date(2024, 5, index), "bb", ["SPD"]) for index in range(2, 7)
    ]

    result = validate_core_parties(poll, comparison_polls=[poll, *comparison_polls])

    assert result.passed is True
    assert result.severity == "warning"
    assert result.affected_parties == ["FDP"]


def test_public_policy_yaml_overrides_public_required_checks(tmp_path) -> None:
    config_path = tmp_path / "validation.toml"
    policy_path = tmp_path / "public_policy.yaml"
    config_path.write_text("", encoding="utf-8")
    policy_path.write_text(
        """
public_dataset:
  required_checks:
    - qc_result_sum_check
core_parties:
  rules:
    - scope: federal
      parties: [SPD]
""",
        encoding="utf-8",
    )

    get_validation_config.cache_clear()
    config = get_validation_config(config_path, policy_path)

    assert config.public_dataset.required_checks == ("qc_result_sum_check",)
    assert config.core_parties.rules[0].parties == ("SPD",)


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
    assert validation.qc_result_sum_check is True
    assert validation.details["public_id"] == "C00000001"
    assert session.query(Poll).one().respondents == 1200

    persisted = service.get_persisted("C00000001")
    assert persisted is not None
    assert persisted.poll_id == poll.id
    assert persisted.valid is True

    report = ValidationReportService(session).build_report()
    assert report.total_polls == 1
    assert report.valid_share == 1.0
    assert report.public_status == "ready"
    assert report.research_ready_polls == 1
    assert report.polls_outside_quality_criteria == 0
    assert report.checks[0].check.startswith("qc_")
    assert report.checks[0].needs_review == report.checks[0].failed


def _poll_with_results(
    poll_id: int,
    publish_date: dt.date,
    scope: str,
    party_keys: list[str],
) -> Poll:
    return Poll(
        id=poll_id,
        publish_date=publish_date,
        scope=scope,
        results=[PollResult(party_key=party_key, percentage=10) for party_key in party_keys],
    )
