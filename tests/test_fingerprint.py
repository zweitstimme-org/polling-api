"""Tests for cleaned poll fingerprints."""

import json
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.cleaner.etl_pipeline import run_cleaning_pipeline
from pollingapi.cleaner.fingerprint import build_poll_fingerprint
from pollingapi.database import Base
from pollingapi.models import Poll, RawPoll


def test_cleaned_fingerprint_includes_provider_and_source() -> None:
    """Provider/source are part of exact cleaned-poll identity."""
    base = {
        "publish_date": date(2024, 1, 10),
        "survey_date_start": date(2024, 1, 5),
        "survey_date_end": date(2024, 1, 8),
        "respondents": 1000,
        "institute_key": "INSA",
        "provider_name": "provider-a",
        "source": "html_scraper",
        "method_key": "ONLINE",
        "election_key": "BUND",
        "scope": "federal",
        "results": {"CDU_CSU": 27.0, "SPD": 18.0},
    }

    same = build_poll_fingerprint(**base)
    different_provider = build_poll_fingerprint(**{**base, "provider_name": "provider-b"})
    different_source = build_poll_fingerprint(**{**base, "source": "api"})

    assert same != different_provider
    assert same != different_source


def test_cleaning_pipeline_skips_duplicate_cleaned_poll(tmp_path) -> None:
    """Raw rows with the same cleaned fingerprint create one cleaned poll."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    raw_values = {
        "publish_date": "2024-01-10",
        "survey_date_start": "2024-01-05",
        "survey_date_end": "2024-01-08",
        "respondents": "1000",
        "zeitraum": None,
        "parties": json.dumps({"CDU/CSU": "27", "SPD": "18"}),
        "institute_id": "INSA",
        "provider": "provider-a",
        "source": "html_scraper",
        "scope": "Bund",
        "election_id": "Bundestagswahl",
        "method_id": "Online",
        "worker": "insa",
        "date_downloaded": "2024-01-11T10:00:00",
    }
    session.add_all([RawPoll(**raw_values), RawPoll(**raw_values)])
    session.commit()

    stats = run_cleaning_pipeline(session)

    assert stats["processed"] == 2
    assert stats["created"] == 1
    assert stats["skipped"] == 1
    assert session.query(Poll).count() == 1
    poll = session.query(Poll).one()
    assert poll.fingerprint is not None
    duplicate_raw = session.query(RawPoll).filter(RawPoll.duplicate_of_poll_id.isnot(None)).one()
    assert duplicate_raw.duplicate_of_poll_id == poll.id


def test_cleaning_pipeline_keeps_same_poll_from_different_provider(tmp_path) -> None:
    """Provider is included, so otherwise identical cleaned polls can coexist."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    raw_values = {
        "publish_date": "2024-01-10",
        "survey_date_start": "2024-01-05",
        "survey_date_end": "2024-01-08",
        "respondents": "1000",
        "zeitraum": None,
        "parties": json.dumps({"CDU/CSU": "27", "SPD": "18"}),
        "institute_id": "INSA",
        "source": "html_scraper",
        "scope": "Bund",
        "election_id": "Bundestagswahl",
        "method_id": "Online",
        "worker": "insa",
        "date_downloaded": "2024-01-11T10:00:00",
    }
    session.add_all(
        [
            RawPoll(**{**raw_values, "provider": "provider-a"}),
            RawPoll(**{**raw_values, "provider": "provider-b"}),
        ]
    )
    session.commit()

    stats = run_cleaning_pipeline(session)

    assert stats["created"] == 2
    assert stats["skipped"] == 0
    assert session.query(Poll).count() == 2
    assert len({poll.fingerprint for poll in session.query(Poll).all()}) == 2


def test_cleaning_pipeline_backfills_existing_poll_fingerprint(tmp_path) -> None:
    """Existing cleaned polls get fingerprints before new raw rows are checked."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    raw_values = {
        "publish_date": "2024-01-10",
        "survey_date_start": "2024-01-05",
        "survey_date_end": "2024-01-08",
        "respondents": "1000",
        "zeitraum": None,
        "parties": json.dumps({"CDU/CSU": "27", "SPD": "18"}),
        "institute_id": "INSA",
        "provider": "provider-a",
        "source": "html_scraper",
        "scope": "Bund",
        "election_id": "Bundestagswahl",
        "method_id": "Online",
        "worker": "insa",
        "date_downloaded": "2024-01-11T10:00:00",
    }
    session.add(RawPoll(**raw_values))
    session.commit()
    run_cleaning_pipeline(session)

    poll = session.query(Poll).one()
    poll.fingerprint = None
    session.add(RawPoll(**raw_values))
    session.commit()

    stats = run_cleaning_pipeline(session)

    assert stats["processed"] == 1
    assert stats["created"] == 0
    assert stats["skipped"] == 1
    assert session.query(Poll).count() == 1
    assert session.query(Poll).one().fingerprint is not None
