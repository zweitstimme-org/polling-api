"""Tests for DAWUM parliament → scope / election mapping and re-ingest."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.models import RawPoll
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.dawum import DawumScraper
from pollingapi.scraper.dawum_parliaments import (
    UnknownDawumParliamentError,
    clear_parliament_catalog_cache,
    map_dawum_parliament,
)


@pytest.fixture(autouse=True)
def _reload_catalog():
    clear_parliament_catalog_cache()
    yield
    clear_parliament_catalog_cache()


EXPECTED_BY_ID = {
    "0": ("federal", "Bundestagswahl"),
    "1": ("bw", "Landtagswahl"),
    "2": ("by", "Landtagswahl"),
    "3": ("be", "Landtagswahl"),
    "4": ("bb", "Landtagswahl"),
    "5": ("hb", "Landtagswahl"),
    "6": ("hh", "Landtagswahl"),
    "7": ("he", "Landtagswahl"),
    "8": ("mv", "Landtagswahl"),
    "9": ("ni", "Landtagswahl"),
    "10": ("nrw", "Landtagswahl"),
    "11": ("rp", "Landtagswahl"),
    "12": ("sl", "Landtagswahl"),
    "13": ("sn", "Landtagswahl"),
    "14": ("st", "Landtagswahl"),
    "15": ("sh", "Landtagswahl"),
    "16": ("th", "Landtagswahl"),
    "17": ("federal", "Europawahl"),
}


@pytest.mark.parametrize(("parliament_id", "expected"), sorted(EXPECTED_BY_ID.items()))
def test_map_dawum_parliament_catalog_ids(parliament_id, expected):
    mapping = map_dawum_parliament(parliament_id)
    assert (mapping.scope, mapping.election_id) == expected


def test_map_dawum_parliament_berlin_live_labels():
    mapping = map_dawum_parliament(
        "3",
        shortcut="Berlin",
        election="Abgeordnetenhauswahl in Berlin",
    )
    assert mapping.scope == "be"
    assert mapping.election_id == "Landtagswahl"


def test_map_dawum_parliament_rejects_unknown_land_label():
    with pytest.raises(UnknownDawumParliamentError):
        map_dawum_parliament("999", shortcut="Atlantis", election="Landtagswahl in Atlantis")


def test_prepare_db_payload_uses_parliament_scope():
    scraper = DawumScraper(db=None, context=RunContext.for_project())
    data = {
        "Parliaments": {
            "0": {"Shortcut": "Bundestag", "Election": "Bundestagswahl"},
            "3": {"Shortcut": "Berlin", "Election": "Abgeordnetenhauswahl in Berlin"},
            "2": {"Shortcut": "Bayern", "Election": "Landtagswahl in Bayern"},
        },
        "Institutes": {"1": {"Name": "Civey"}, "2": {"Name": "INSA"}},
        "Taskers": {"1": {"Name": "Der Tagesspiegel"}},
        "Methods": {"1": {"Name": "Online"}},
        "Parties": {"1": {"Shortcut": "SPD"}, "2": {"Shortcut": "CDU"}, "3": {"Shortcut": "CSU"}},
        "Surveys": {
            "100": {
                "Date": "2026-08-05",
                "Survey_Period": {"Date_Start": "2026-07-20", "Date_End": "2026-08-03"},
                "Surveyed_Persons": "3000",
                "Parliament_ID": "3",
                "Institute_ID": "1",
                "Tasker_ID": "1",
                "Method_ID": "1",
                "Results": {"1": 12, "2": 19},
            },
            "101": {
                "Date": "2026-08-04",
                "Survey_Period": {"Date_Start": "2026-07-28", "Date_End": "2026-08-02"},
                "Surveyed_Persons": "1000",
                "Parliament_ID": "0",
                "Institute_ID": "2",
                "Tasker_ID": "1",
                "Method_ID": "1",
                "Results": {"1": 15, "2": 30},
            },
            "102": {
                "Date": "2026-07-18",
                "Survey_Period": {"Date_Start": "2026-07-10", "Date_End": "2026-07-15"},
                "Surveyed_Persons": "5000",
                "Parliament_ID": "2",
                "Institute_ID": "1",
                "Tasker_ID": "1",
                "Method_ID": "1",
                "Results": {"3": 37, "1": 6},
            },
        },
    }
    df = scraper.wrangle_data(data)
    payloads = scraper.prepare_db_payload(df)
    by_date = {p["publish_date"]: p for p in payloads}
    assert by_date["2026-08-05"]["scope"] == "be"
    assert by_date["2026-08-05"]["election_id"] == "Landtagswahl"
    assert by_date["2026-08-04"]["scope"] == "federal"
    assert by_date["2026-08-04"]["election_id"] == "Bundestagswahl"
    assert by_date["2026-07-18"]["scope"] == "by"
    assert by_date["2026-07-18"]["election_id"] == "Landtagswahl"


def test_post_polls_updates_scope_in_place_without_duplicate(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'dawum.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    parties = {"CDU": 19.0, "SPD": 12.0, "LINKE": 21.0}
    session.add(
        RawPoll(
            publish_date="2026-08-05",
            survey_date_start="2026-07-20",
            survey_date_end="2026-08-03",
            respondents="3000",
            parties=json.dumps(parties, sort_keys=True),
            institute_id="Civey",
            provider="DAWUM",
            tasker="Der Tagesspiegel",
            source="api",
            scope="federal",
            election_id="Bundestagswahl",
            method_id="Online",
            worker="dawum",
        )
    )
    session.commit()

    scraper = DawumScraper(db=session, context=RunContext.for_project())
    payload = {
        "publish_date": "2026-08-05",
        "survey_date_start": "2026-07-20",
        "survey_date_end": "2026-08-03",
        "respondents": "3000",
        "parties": parties,
        "institute_id": "Civey",
        "provider": "DAWUM",
        "tasker": "Der Tagesspiegel",
        "source": "api",
        "scope": "be",
        "election_id": "Landtagswahl",
        "method_id": "Online",
        "worker": "dawum",
        "survey_type": None,
        "zeitraum": None,
    }

    changed = scraper.post_polls([payload])
    assert changed == 1
    assert session.query(func.count(RawPoll.id)).scalar() == 1
    row = session.query(RawPoll).one()
    assert row.scope == "be"
    assert row.election_id == "Landtagswahl"

    # Second run is a no-op (no duplicate, no extra update count noise beyond skip)
    changed_again = scraper.post_polls([payload])
    assert changed_again == 0
    assert session.query(func.count(RawPoll.id)).scalar() == 1
