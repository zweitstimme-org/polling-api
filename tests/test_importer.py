"""Tests for file imports into raw polls."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.importer.runner import ImportRunner
from pollingapi.importer.sources import get_source, list_sources
from pollingapi.models import Poll, PollResult, RawPoll


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_csv_source_preserves_party_column_names(tmp_path):
    path = tmp_path / "polls.csv"
    path.write_text(
        "publish_date,institut,scope,election_id,respondents,CDU/CSU,SPD\n"
        "2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16\n",
        encoding="utf-8",
    )

    rows = get_source("csv").load(path)

    assert len(rows) == 1
    assert rows[0].parties == {"CDU/CSU": "30", "SPD": "16"}
    assert rows[0].to_raw_dict()["worker"] == "import:csv"


def test_import_runner_inserts_and_dedupes_raw_rows(tmp_path):
    session = _session(tmp_path)
    path = tmp_path / "polls.csv"
    path.write_text(
        "publish_date,institut,scope,election_id,respondents,CDU/CSU,SPD\n"
        "2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16\n",
        encoding="utf-8",
    )
    runner = ImportRunner(session, imports_dir=tmp_path)

    first = runner.run("csv", "polls.csv")
    second = runner.run("csv", "polls.csv")

    assert first.stats.parsed == 1
    assert first.stats.inserted == 1
    assert first.stats.skipped == 0
    assert second.stats.inserted == 0
    assert second.stats.skipped == 1
    assert session.query(RawPoll).count() == 1


def test_import_runner_dedupes_repeated_rows_in_same_file(tmp_path):
    session = _session(tmp_path)
    path = tmp_path / "polls.csv"
    path.write_text(
        "publish_date,institut,scope,election_id,respondents,CDU/CSU,SPD\n"
        "2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16\n"
        "2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16\n",
        encoding="utf-8",
    )
    runner = ImportRunner(session, imports_dir=tmp_path)

    result = runner.run("csv", "polls.csv")

    assert result.stats.inserted == 1
    assert result.stats.skipped == 1
    assert session.query(RawPoll).count() == 1


def test_import_runner_can_clean_imported_rows(tmp_path):
    session = _session(tmp_path)
    path = tmp_path / "polls.csv"
    path.write_text(
        "publish_date,institut,scope,election_id,respondents,CDU/CSU,SPD\n"
        "2024-06-01,Forsa,Bund,Bundestagswahl,1000,30,16\n",
        encoding="utf-8",
    )
    runner = ImportRunner(session, imports_dir=tmp_path)

    result = runner.run("csv", path, clean=True)

    assert result.stats.inserted == 1
    assert result.cleaning_stats is not None
    assert result.cleaning_stats["created"] == 1
    assert session.query(Poll).count() == 1
    assert {result.party_key for result in session.query(PollResult).all()} == {"CDU_CSU", "SPD"}


def test_import_sources_are_listed():
    assert list_sources() == ["csv", "manual_csv"]
