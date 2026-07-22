"""Tests for CLI commands."""

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from pollingapi import cli
from pollingapi.database import Base
from pollingapi.models import Institute, Party, Poll, PollResult, RawPoll


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_polls_by_date_finds_cleaned_polls(tmp_path, monkeypatch):
    session = _session(tmp_path)
    institute = Institute(key="FORSA", name="Forsa")
    raw_poll = RawPoll(public_id="R00000001", publish_date="2024-06-01")
    poll = Poll(
        public_id="C00000001",
        raw_poll=raw_poll,
        publish_date=dt.date(2024, 6, 1),
        respondents=1200,
        scope="federal",
        election_key="BTW",
        institute=institute,
        results=[
            PollResult(party_key="CDU_CSU", percentage=30),
            PollResult(party_key="SPD", percentage=20),
        ],
    )
    session.add_all(
        [
            Party(key="CDU_CSU", name="CDU/CSU", short_name="Union"),
            Party(key="SPD", name="SPD", short_name="SPD"),
            poll,
        ]
    )
    session.commit()
    monkeypatch.setattr(cli, "get_db", lambda: session)

    result = CliRunner().invoke(cli.app, ["polls:date", "2024", "06", "01"])

    assert result.exit_code == 0
    assert "Found 1 poll(s) for 2024-06-01" in result.output
    assert "C00000001 | raw=R00000001 | institute=Forsa" in result.output
    assert "CDU_CSU 30" in result.output
    assert "SPD 20" in result.output


def test_polls_by_date_reports_no_matches(tmp_path, monkeypatch):
    session = _session(tmp_path)
    monkeypatch.setattr(cli, "get_db", lambda: session)

    result = CliRunner().invoke(cli.app, ["polls:date", "2024", "06", "01"])

    assert result.exit_code == 0
    assert "No polls found for 2024-06-01" in result.output


def test_polls_by_date_rejects_invalid_dates():
    result = CliRunner().invoke(cli.app, ["polls:date", "2024", "02", "31"])

    assert result.exit_code != 0
    assert "Expected yyyy mm dd" in result.output
