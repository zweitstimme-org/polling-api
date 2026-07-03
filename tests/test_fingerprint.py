"""Tests for raw poll content fingerprints."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.models import RawPoll
from pollingapi.scraper.datamodel import BundElectionPoll, SourcePartyResult
from pollingapi.scraper.fingerprint import (
    FINGERPRINT_FIELDS,
    build_content_fingerprint,
    build_content_hash,
)
from pollingapi.scraper.insertion import insert_new_polls


def _raw_dict(**overrides):
    data = {
        "publish_date": "2024-01-10",
        "scope": "federal",
        "election_id": "BUND",
        "institute_id": "INSA",
        "survey_type": "poll",
        "provider": "provider-a",
        "source": "html_scraper",
        "worker": "insa",
        "date_downloaded": "2024-01-11T10:00:00",
        "parties": '{"CDU/CSU": "27", "SPD": "18"}',
    }
    data.update(overrides)
    return data


def test_fingerprint_documents_selected_columns() -> None:
    assert FINGERPRINT_FIELDS == (
        "scope",
        "election_id",
        "publish_year",
        "publish_week",
        "institute_id",
        "survey_type",
        "union_share",
        "spd_share",
    )


def test_hash_ignores_provider_source_worker_and_download_time() -> None:
    first = build_content_hash(_raw_dict())
    second = build_content_hash(
        _raw_dict(
            provider="provider-b",
            source="api",
            worker="dawum",
            date_downloaded="2024-01-12T10:00:00",
        )
    )

    assert first == second


def test_hash_changes_when_core_vote_share_changes() -> None:
    first = build_content_hash(_raw_dict())
    second = build_content_hash(_raw_dict(parties='{"CDU/CSU": "27", "SPD": "19"}'))

    assert first != second


def test_fingerprint_uses_year_and_iso_week_from_publish_date() -> None:
    fingerprint = build_content_fingerprint(_raw_dict(publish_date="10.01.2024"))

    assert "publish_year=2024" in fingerprint
    assert "publish_week=02" in fingerprint


def test_insert_new_polls_deduplicates_by_content_hash() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    poll = BundElectionPoll(
        scraped_at=datetime(2024, 1, 11, 10, 0),
        data_source="provider-a",
        worker="insa",
        scope="BUND",
        state="federal",
        institut="INSA",
        datum="2024-01-10",
        befragte="1000",
        zeitraum="",
        results=[
            SourcePartyResult(name="CDU/CSU", value="27"),
            SourcePartyResult(name="SPD", value="18"),
        ],
    )

    inserted, skipped = insert_new_polls(
        session,
        [poll],
        provider="provider-a",
        source="html_scraper",
        election_id="BUND",
        method_id="UNBEKANNT",
        pipeline_run_id=None,
    )
    inserted_again, skipped_again = insert_new_polls(
        session,
        [poll],
        provider="provider-b",
        source="api",
        election_id="BUND",
        method_id="UNBEKANNT",
        pipeline_run_id=None,
    )

    assert (inserted, skipped) == (1, 0)
    assert (inserted_again, skipped_again) == (0, 1)
    assert session.query(RawPoll).count() == 1
    assert session.query(RawPoll).one().content_hash is not None
