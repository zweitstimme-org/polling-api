"""Wahlrecht.de Europawahl federal scraper."""

import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.datamodel import BundElectionPoll, GermanState, SourcePartyResult
from pollingapi.scraper.insertion import insert_new_polls
from pollingapi.scraper.snapshots import save_html_snapshot


class EuFedCurrentScraper:
    URL = "https://www.wahlrecht.de/umfragen/europawahl.htm"
    WORKER = "eu_fed"
    STATE: str = GermanState.BUND
    SCOPE = "Europawahl"
    DATA_SOURCE = "wahlrecht.de"
    TABLES = (0, 1)
    REQUEST_DELAY = 1.0

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
        date_str = self.context.today_str if self.context else datetime.now().strftime("%Y-%m-%d")
        save_html_snapshot(self.WORKER, self.URL, html, date_str)

    @staticmethod
    def _text(cell) -> str:
        return re.sub(r"\s+", " ", cell.get_text(" ", strip=True).replace("\xa0", " ")).strip()

    def _party_headers(self, table) -> list[str]:
        headers = [self._text(th) for th in table.select("thead th")]
        return [header for header in headers[6:] if header]

    def _party_results(self, cells, headers: list[str]) -> list[SourcePartyResult]:
        results: list[SourcePartyResult] = []
        index = 0
        for cell in cells:
            value = self._text(cell)
            colspan = int(cell.get("colspan", 1))
            if not value:
                index += colspan
                continue

            if colspan == 2 and headers[index : index + 2] == ["CDU", "CSU"]:
                name = "CDU/CSU"
            elif index < len(headers):
                name = headers[index]
            else:
                break

            results.append(SourcePartyResult(name=name, value=value))
            index += colspan
        return results

    def _row_to_poll(
        self,
        cells,
        party_headers: list[str],
        state: str,
        date_pattern: str = r"^\d{2}\.\d{2}\.\d{4}$",
    ) -> BundElectionPoll | None:
        if len(cells) < 7:
            return None

        date_or_institute = self._text(cells[0])
        if not re.match(date_pattern, date_or_institute):
            return None

        parties = self._party_results(cells[6:], party_headers)
        if not parties:
            return None

        return BundElectionPoll(
            data_source=self.DATA_SOURCE,
            worker=self.WORKER,
            scope=self.SCOPE,
            state=state,
            institut=self._text(cells[2]),
            auftraggeber=self._text(cells[3]) or None,
            datum=date_or_institute,
            befragte=self._text(cells[4]),
            zeitraum="",
            results=parties,
        )

    def _parse_table(self, table) -> list[BundElectionPoll]:
        party_headers = self._party_headers(table)
        polls: list[BundElectionPoll] = []
        for row in table.select("tbody tr"):
            poll = self._row_to_poll(
                row.find_all(["td", "th"], recursive=False), party_headers, self.STATE
            )
            if poll:
                polls.append(poll)
        return polls

    def parse(self, html: str) -> list[BundElectionPoll]:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table", class_="wilko")
        polls: list[BundElectionPoll] = []
        for index in self.TABLES:
            if index < len(tables):
                polls.extend(self._parse_table(tables[index]))
        return polls

    def insert(self, polls: list[BundElectionPoll]) -> int:
        inserted, skipped = insert_new_polls(
            db=self.db,
            polls=polls,
            provider=self.DATA_SOURCE,
            source="html_scraper",
            election_id=self.SCOPE,
            method_id="99",
            pipeline_run_id=self.context.run_id if self.context else None,
        )
        self.logger.info(f"Inserted {inserted} polls for {self.WORKER} (skipped {skipped})")
        return inserted

    def run(self) -> int:
        html = self.fetch()
        self.save_snapshot(html)
        return self.insert(self.parse(html))
