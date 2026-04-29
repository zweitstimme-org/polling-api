import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.datamodel import GermanState, LandElectionPoll, SourcePartyResult
from pollingapi.scraper.insertion import insert_new_polls
from pollingapi.scraper.snapshots import save_html_snapshot


class BYBaseScraper:
    URL: str = ""
    WORKER: str = ""
    STATE = GermanState.BY
    SCOPE: str = "Landtagswahl"
    INSTITUTE: str = ""
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}

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

    def _normalize_text(self, value: str) -> str:
        return value.replace("\xa0", " ").strip()

    def _extract_headers(self, table) -> list[str]:
        headers = [self._normalize_text(th.get_text()) for th in table.select("thead th")]

        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [
                    self._normalize_text(th.get_text()) for th in first_row.find_all(["th", "td"])
                ]

        if headers and headers[0] == "":
            headers[0] = "Datum"

        return headers

    def _extract_row_data(self, headers: list[str], tr) -> dict[str, str] | None:
        cells = tr.find_all("td")
        if len(cells) < len(headers):
            return None

        return {headers[i]: self._normalize_text(cells[i].get_text()) for i in range(len(headers))}

    def _extract_parties(self, row_data: dict[str, str]) -> list[SourcePartyResult]:
        parties: list[SourcePartyResult] = []
        for key, value in row_data.items():
            if not key or key in self.META_KEYS:
                continue
            if not value:
                continue
            parties.append(SourcePartyResult(name=key, value=value))
        return parties

    def parse(self, html: str) -> list[LandElectionPoll]:
        self.logger.info("Parsing HTML content...")
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table", class_="wilko")
        if not tables:
            self.logger.warning("No tables with class '.wilko' found.")
            return []

        extracted_polls: list[LandElectionPoll] = []

        for table_idx, table in enumerate(tables):
            self.logger.info(f"Processing table {table_idx + 1} of {len(tables)}...")

            headers = self._extract_headers(table)
            if not headers:
                self.logger.debug(f"Table {table_idx} has no headers, skipping.")
                continue

            rows = table.select("tbody tr")
            if not rows:
                rows = table.find_all("tr")[1:]

            for row_idx, tr in enumerate(rows):
                row_data = self._extract_row_data(headers, tr)
                if not row_data:
                    continue

                try:
                    parties = self._extract_parties(row_data)
                    if not parties:
                        continue

                    poll = LandElectionPoll(
                        data_source=self.DATA_SOURCE,
                        worker=self.WORKER,
                        scope=self.SCOPE,
                        state=self.STATE,
                        institut=row_data.get("Institut", self.INSTITUTE),
                        befragte=row_data.get("Befragte", ""),
                        auftraggeber=row_data.get("Auftraggeber") or None,
                        datum=row_data.get("Datum", ""),
                        zeitraum=row_data.get("Zeitraum", ""),
                        results=parties,
                    )
                    extracted_polls.append(poll)

                except Exception:
                    self.logger.debug(f"Table {table_idx} Row {row_idx} failed validation.")

        return extracted_polls

    def insert(self, polls: list[LandElectionPoll]) -> int:
        if not polls:
            return 0

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
        polls = self.parse(html)
        return self.insert(polls)


class BYCurrentScraper(BYBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/landtage/bayern.htm"
    WORKER = "bayern_current"
    SCOPE = "Landtagswahl"
    INSTITUTE = ""
    DATA_SOURCE = "wahlrecht.de"
