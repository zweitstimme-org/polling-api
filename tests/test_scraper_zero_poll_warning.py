"""Tests for scraper zero-poll warning detection."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pollingapi.database import Base
from pollingapi.models import RawPoll
from pollingapi.scraper.runner import ScraperRunner


class EmptyHtmlScraper:
    """Minimal HTML scraper double used by ScraperRunner."""

    def fetch(self) -> str:
        return "<html></html>"

    def save_snapshot(self, html: str) -> None:
        pass

    def parse(self, html: str) -> list:
        return []

    def insert(self, polls: list) -> int:
        return 0


def test_zero_poll_warning_requires_prior_raw_polls(tmp_path):
    """A zero-poll parse only warns for workers with existing raw poll history."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    runner = ScraperRunner(session)

    runner._run_scraper("new_worker", EmptyHtmlScraper())

    assert runner.zero_poll_workers == []


def test_zero_poll_warning_records_previously_working_worker(tmp_path):
    """A worker that previously inserted raw polls warns when it now finds none."""
    engine = create_engine(f"sqlite:///{tmp_path / 'polling.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(RawPoll(worker="known_worker"))
    session.commit()
    runner = ScraperRunner(session)

    runner._run_scraper("known_worker", EmptyHtmlScraper())

    assert runner.zero_poll_workers == ["known_worker"]
