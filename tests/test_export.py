"""Tests for public data exports."""

import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.core import settings
from pollingapi.database import Base
from pollingapi.models import (
    Election,
    Institute,
    Method,
    Party,
    Poll,
    PollResult,
    Provider,
    RawPoll,
)
from pollingapi.services.export import ExportService


def _seed_export_fixture(session) -> None:
    raw = RawPoll(
        publish_date="2024-06-01",
        survey_date_start="2024-05-24",
        survey_date_end="2024-05-28",
        respondents="1000",
        parties=json.dumps({"CDU/CSU": "30", "SPD": "16"}),
        institute_id="Forsa",
        provider="wahlrecht.de",
        source="html_scraper",
        scope="Bund",
        election_id="Bundestagswahl",
        method_id="Online",
        worker="forsa_current",
        date_downloaded="2024-06-01T12:00:00",
    )
    provider = Provider(name="wahlrecht.de")
    institute = Institute(key="FORSA", name="Forsa")
    method = Method(key="ONLINE", name="Online")
    election = Election(key="BUND", election_type="Bundestagswahl", scope="federal")
    parties = [
        Party(key="CDU_CSU", name="CDU/CSU", short_name="CDU/CSU"),
        Party(key="SPD", name="Sozialdemokratische Partei Deutschlands", short_name="SPD"),
    ]
    session.add_all([raw, provider, institute, method, election, *parties])
    session.flush()

    poll = Poll(
        raw_id=raw.id,
        publish_date=date(2024, 6, 1),
        survey_date_start=date(2024, 5, 24),
        survey_date_end=date(2024, 5, 28),
        respondents=1000,
        institute_key="FORSA",
        provider_id=provider.id,
        election_key="BUND",
        method_key="ONLINE",
        source="html_scraper",
        scope="federal",
        fingerprint="test-fingerprint",
        date_downloaded=datetime(2024, 6, 1, 12, 0),
    )
    session.add(poll)
    session.flush()
    session.add_all(
        [
            PollResult(poll_id=poll.id, party_key="CDU_CSU", percentage=30.0),
            PollResult(poll_id=poll.id, party_key="SPD", percentage=16.0),
        ]
    )
    session.commit()


def test_export_all_writes_self_contained_bundle(tmp_path, monkeypatch):
    """Export bundle contains polls, observations, wide rows, raw rows, dictionaries, and metadata."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    _seed_export_fixture(session)
    export_dir = tmp_path / "export"
    monkeypatch.setattr(settings, "export_dir", export_dir)

    counts = ExportService(session).export_all()

    assert counts["polls"] == 1
    assert counts["observations"] == 2
    assert counts["wide"] == 1
    assert counts["raw"] == 1
    assert (export_dir / "polls.json").exists()
    assert (export_dir / "observations.csv").exists()
    assert (export_dir / "polls_wide.csv").exists()
    assert (export_dir / "polls_raw.json").exists()
    assert (export_dir / "poll_results.json").exists()
    assert (export_dir / "dictionaries" / "institutes.json").exists()

    polls = json.loads((export_dir / "polls.json").read_text(encoding="utf-8"))
    assert polls[0]["poll_public_id"].startswith("C")
    assert polls[0]["provider"]["name"] == "wahlrecht.de"
    assert polls[0]["institute"]["key"] == "FORSA"
    assert {result["party_key"] for result in polls[0]["results"]} == {"CDU_CSU", "SPD"}

    institutes = json.loads(
        (export_dir / "dictionaries" / "institutes.json").read_text(encoding="utf-8")
    )
    assert institutes == [{"key": "FORSA", "name": "Forsa", "description": None}]

    metadata = json.loads((export_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["counts"]["polls"] == 1
    assert "dictionaries/institutes.json" in metadata["datasets"]["dictionaries"]["files"]
