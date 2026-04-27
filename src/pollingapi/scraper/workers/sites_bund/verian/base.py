import time
from abc import abstractmethod

import requests
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.models import RawPoll
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.datamodel import BundElectionPoll
from pollingapi.scraper.scraper_insertion import poll_to_raw_dict
from pollingapi.scraper.snapshots import save_html_snapshot


class VerianBaseScraper:
    URL: str = ""
    WORKER: str = ""
    STATE: str = "Bund"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0

    def __init__(self, db: Session, context: RunContext | None = None):
        self.db = db
        self.context = context
        self.logger = get_logger(self.WORKER)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Scraper/1.0"}
        )

    def fetch(self) -> str:
        self.logger.info(f"Fetching: {self.URL}")
        time.sleep(self.REQUEST_DELAY)
        response = self.session.get(self.URL, timeout=15)
        response.raise_for_status()
        return response.text

    def save_snapshot(self, html: str) -> None:
        date_str = (
            self.context.today_str
            if self.context
            else __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        )
        save_html_snapshot(self.WORKER, self.URL, html, date_str)

    def insert(self, polls: list[BundElectionPoll]) -> int:
        if not polls:
            return 0
        inserted = 0
        for poll in polls:
            raw_dict = poll_to_raw_dict(
                poll,
                provider=self.DATA_SOURCE,
                source="html_scraper",
                election_id=self.SCOPE,
                method_id="99",
                pipeline_run_id=self.context.run_id if self.context else None,
            )
            raw_poll = RawPoll(**raw_dict)
            self.db.add(raw_poll)
            inserted += 1
        self.db.commit()
        self.logger.info(f"Inserted {inserted} polls for {self.WORKER}")
        return inserted

    def run(self) -> int:
        html = self.fetch()
        self.save_snapshot(html)
        polls = self.parse(html)
        return self.insert(polls)

    @abstractmethod
    def parse(self, html: str) -> list[BundElectionPoll]:
        """Each worker implements its own parsing."""
        pass
