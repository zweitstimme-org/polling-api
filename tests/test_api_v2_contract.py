"""Contract tests for the public v2 API."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pollingapi.api import v2
from pollingapi.data_validation.config import PublicDatasetConfig
from pollingapi.database import Base, get_db
from pollingapi.main import app
from pollingapi.models import Party, Poll, PollResult, PollValidation, RawPoll


@pytest.fixture
def v2_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Create an isolated API client with deterministic poll validation rows."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        _seed_v2_contract_data(session)

    def override_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    monkeypatch.setattr(
        v2,
        "get_validation_config",
        lambda: SimpleNamespace(
            public_dataset=PublicDatasetConfig(
                require_persisted_validation=True,
                include_valid=True,
                include_warnings=True,
                exclude_failed_checks=(),
            )
        ),
    )
    app.dependency_overrides[get_db] = override_db
    with (
        patch("pollingapi.main.init_db_async", return_value=None),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        yield client
    app.dependency_overrides.clear()


def test_v2_default_polls_returns_validated_public_dataset(v2_client: TestClient) -> None:
    response = v2_client.get("/v2/polls?sort=id&include_results=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 2
    assert [item["public_id"] for item in payload["data"]] == ["C00000001", "C00000002"]
    assert all(item["results"] == [] for item in payload["data"])


def test_v2_all_cleaned_dataset_keeps_unvalidated_and_invalid_polls(
    v2_client: TestClient,
) -> None:
    response = v2_client.get("/v2/datasets/all-cleaned/polls?sort=id&include_results=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 5
    assert [item["public_id"] for item in payload["data"]] == [
        "C00000001",
        "C00000002",
        "C00000003",
        "C00000004",
        "C00000005",
    ]


def test_v2_poll_results_follow_default_dataset_policy(v2_client: TestClient) -> None:
    response = v2_client.get("/v2/poll-results?sort=id")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 2
    assert {item["poll_public_id"] for item in payload["data"]} == {
        "C00000001",
        "C00000002",
    }


def test_v2_can_exclude_warning_polls_from_public_dataset(
    v2_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        v2,
        "get_validation_config",
        lambda: SimpleNamespace(
            public_dataset=PublicDatasetConfig(
                require_persisted_validation=True,
                include_valid=True,
                include_warnings=False,
                exclude_failed_checks=(),
            )
        ),
    )

    response = v2_client.get("/v2/polls?sort=id&include_results=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["data"][0]["public_id"] == "C00000001"


def test_v2_default_polls_excludes_non_public_polls(v2_client: TestClient) -> None:
    response = v2_client.get("/v2/polls?sort=id&include_results=false")

    assert response.status_code == 200
    payload = response.json()
    assert "C00000005" not in [item["public_id"] for item in payload["data"]]


def test_v2_poll_payload_uses_english_public_field_names(v2_client: TestClient) -> None:
    response = v2_client.get("/v2/polls?sort=id&limit=1")

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert {
        "published_date",
        "survey_start_date",
        "survey_end_date",
        "survey_method_key",
        "raw_poll_public_id",
    } <= item.keys()
    assert {"publish_date", "method_key", "raw_public_id"}.isdisjoint(item.keys())


def test_v2_raw_poll_payload_uses_english_public_field_names(v2_client: TestClient) -> None:
    response = v2_client.get("/v2/raw-polls?limit=1&sort=id")

    assert response.status_code == 200
    item = response.json()["data"][0]
    assert {
        "published_date_raw",
        "survey_period_raw",
        "party_results_raw",
        "commissioner_raw",
        "survey_method_raw",
    } <= item.keys()
    assert {"publish_date", "zeitraum", "parties", "tasker", "method_id"}.isdisjoint(item.keys())


def _seed_v2_contract_data(session: Session) -> None:
    session.add(Party(key="SPD", name="Social Democratic Party", short_name="SPD"))
    session.add(
        RawPoll(
            public_id="R00000001",
            publish_date="2024-01-01",
            survey_date_start="2023-12-20",
            survey_date_end="2023-12-22",
            respondents="1000",
            zeitraum="20.12.-22.12.2023",
            parties='{"SPD": 20}',
            institute_id="Forsa",
            provider="wahlrecht.de",
            tasker="Example commissioner",
            source="html_scraper",
            scope="Bundestagswahl",
            election_id="Bundestagswahl",
            method_id="Online",
            date_downloaded="2024-01-01T12:00:00",
        )
    )
    session.flush()

    polls = [
        Poll(
            id=1,
            public_id="C00000001",
            raw_id=1,
            publish_date=dt.date(2024, 1, 1),
            survey_date_start=dt.date(2023, 12, 20),
            survey_date_end=dt.date(2023, 12, 22),
            respondents=1000,
            method_key="ONLINE",
            scope="federal",
            source="html_scraper",
            is_public=True,
        ),
        Poll(
            id=2,
            public_id="C00000002",
            publish_date=dt.date(2024, 1, 2),
            survey_date_start=dt.date(2023, 12, 21),
            survey_date_end=dt.date(2023, 12, 23),
            respondents=1100,
            method_key="ONLINE",
            scope="federal",
            source="html_scraper",
            is_public=True,
        ),
        Poll(
            id=3,
            public_id="C00000003",
            publish_date=dt.date(2024, 1, 3),
            survey_date_start=dt.date(2023, 12, 22),
            survey_date_end=dt.date(2023, 12, 24),
            respondents=1200,
            method_key="ONLINE",
            scope="federal",
            source="html_scraper",
            is_public=True,
        ),
        Poll(
            id=4,
            public_id="C00000004",
            publish_date=dt.date(2024, 1, 4),
            survey_date_start=dt.date(2023, 12, 23),
            survey_date_end=dt.date(2023, 12, 25),
            respondents=1300,
            method_key="ONLINE",
            scope="federal",
            source="html_scraper",
            is_public=True,
        ),
        Poll(
            id=5,
            public_id="C00000005",
            publish_date=dt.date(2024, 1, 5),
            survey_date_start=dt.date(2023, 12, 24),
            survey_date_end=dt.date(2023, 12, 26),
            respondents=1400,
            method_key="ONLINE",
            scope="federal",
            source="html_scraper",
            is_public=False,
            public_exclusion_reason="matched_secondary_provider",
        ),
    ]
    session.add_all(polls)
    session.flush()
    session.add_all(
        [PollResult(poll_id=poll.id, party_key="SPD", percentage=20 + poll.id) for poll in polls]
    )
    session.add_all(
        [
            _validation(poll_id=1, valid=True, warning_count=0),
            _validation(poll_id=2, valid=True, warning_count=1),
            _validation(poll_id=3, valid=False, warning_count=0),
            _validation(poll_id=5, valid=True, warning_count=0),
        ]
    )
    session.commit()


def _validation(*, poll_id: int, valid: bool, warning_count: int) -> PollValidation:
    return PollValidation(
        poll_id=poll_id,
        validated_at=dt.datetime(2024, 1, 10, 12, 0, 0),
        valid=valid,
        error_count=0 if valid else 1,
        warning_count=warning_count,
        qc_party_percentage_range=True,
        qc_result_sum_check=valid,
        qc_date_consistency=True,
        qc_respondents_plausible=True,
        qc_core_parties_present=True,
        qc_institute_result_jump=warning_count == 0,
        qc_scope_result_jump=True,
        details={},
    )
