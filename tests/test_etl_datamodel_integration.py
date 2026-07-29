"""Integration tests for datamodel-backed cleaned tables."""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.cleaner.etl_pipeline import run_cleaning_pipeline
from pollingapi.database import Base
from pollingapi.database_seed import seed_all_from_json
from pollingapi.models import Party, Poll, PollResult, RawPoll


def test_cleaning_pipeline_writes_enum_party_keys(tmp_path):
    """Cleaned party results use enum member keys, not numeric DAWUM IDs."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    seed_all_from_json(session)
    session.add(
        RawPoll(
            publish_date="2024-06-01",
            respondents="O • 1.00024.05.–28.05.",
            zeitraum=None,
            parties=json.dumps({"CDU/CSU": "30,5", "SPD": "16", "Summe": "100"}),
            institute_id="Forsa",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="Bund",
            election_id="Bundestagswahl",
            method_id="99",
            worker="test",
            date_downloaded="2024-06-01T12:00:00",
        )
    )
    session.commit()

    stats = run_cleaning_pipeline(session)

    assert stats["created"] == 1
    poll = session.query(Poll).one()
    raw = session.query(RawPoll).one()
    assert raw.public_id == "R00000001"
    assert poll.public_id == "C00000001"
    assert poll.survey_date_start.isoformat() == "2024-05-24"
    assert poll.survey_date_end.isoformat() == "2024-05-28"
    assert poll.institute_key == "FORSA"
    assert poll.method_key == "ONLINE"
    assert poll.election_key == "BUND"
    assert poll.scope == "federal"
    assert {result.party_key for result in session.query(PollResult).all()} == {
        "CDU_CSU",
        "SPD",
    }
    assert session.query(Party).filter(Party.key == "CDU_CSU").one().short_name == "CDU/CSU"


def test_cleaning_pipeline_preserves_eu_election_key(tmp_path):
    """Europawahl raw polls use the EU election key, not their regional scope key."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    seed_all_from_json(session)
    session.add(
        RawPoll(
            publish_date="2024-06-01",
            respondents="O • 1.000",
            zeitraum="24.05.–28.05.",
            parties=json.dumps({"CDU/CSU": "30,5", "SPD": "16"}),
            institute_id="Forsa",
            provider="Wahlrecht.de",
            source="html_scraper",
            scope="BW",
            election_id="Europawahl",
            method_id="Online",
            worker="eu_state",
            date_downloaded="2024-06-01T12:00:00",
        )
    )
    session.commit()

    stats = run_cleaning_pipeline(session)

    assert stats["created"] == 1
    poll = session.query(Poll).one()
    assert poll.election_key == "EU_WAHLEN"
    assert poll.scope == "bw"
