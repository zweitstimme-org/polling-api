import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.datamodel import BundElectionPoll, GermanState, PartyResult
from pollingapi.scraper.insertion import insert_new_polls
from pollingapi.scraper.snapshots import save_html_snapshot


# implementation of the base class in this file
class AllensbachBaseScraper:
    URL: str = ""
    WORKER: str = ""
    STATE = GermanState.BUND
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
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

    def _extract_parties(self, row_data: dict[str, str]) -> list[PartyResult]:
        parties: list[PartyResult] = []
        for key, value in row_data.items():
            if not key or key in self.META_KEYS:
                continue
            if not value:
                continue
            parties.append(PartyResult(name=key, value=value))
        return parties

    def parse(self, html: str) -> list[BundElectionPoll]:
        self.logger.info("Parsing HTML content...")
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table", class_="wilko")
        if not tables:
            self.logger.warning("No tables with class '.wilko' found.")
            return []

        extracted_polls: list[BundElectionPoll] = []

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

                    poll = BundElectionPoll(
                        data_source=self.DATA_SOURCE,
                        worker=self.WORKER,
                        scope=self.SCOPE,
                        state=self.STATE,
                        institut=self.INSTITUTE,
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

    def insert(self, polls: list[BundElectionPoll]) -> int:
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


# This worker targets the main site and therefore is the one to keep in check first
class AllensbachCurrentScraper(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach.htm"
    WORKER = "allensbach_current"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2017Scraper(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2013.htm"
    STATE: str = GermanState.BUND
    WORKER = "allensbach_2017"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


# with the end of 2013 there are no more east west differences
class Allensbach2013Total(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2013.htm"
    WORKER = "allensbach_2017_total"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2013Ost(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2013o.htm"
    STATE = GermanState.OST
    WORKER = "allensbach_2017_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2013West(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2013w.htm"
    STATE = GermanState.WEST
    WORKER = "allensbach_2017_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2009Total(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2009.htm"
    WORKER = "allensbach_2009_total"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2009Ost(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2009o.htm"
    STATE = GermanState.OST
    WORKER = "allensbach_2009_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2009West(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2009w.htm"
    STATE = GermanState.WEST
    WORKER = "allensbach_2009_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2005Total(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2005.htm"
    WORKER = "allensbach_2005_total"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2005Ost(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2005o.htm"
    STATE = GermanState.OST
    WORKER = "allensbach_2005_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2005West(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2005w.htm"
    STATE = GermanState.WEST
    WORKER = "allensbach_2005_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2002Total(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2002.htm"
    STATE: str = GermanState.BUND
    WORKER = "allensbach_2002_total"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2002Ost(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2002o.htm"
    STATE: str = GermanState.OST
    WORKER = "allensbach_2002_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Allensbach2002West(AllensbachBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/allensbach/2002w.htm"
    STATE: str = GermanState.WEST
    WORKER = "allensbach_2002_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Allensbach"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}
