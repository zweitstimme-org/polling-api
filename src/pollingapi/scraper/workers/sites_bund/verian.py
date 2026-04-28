import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from pollingapi.logging_config import get_logger
from pollingapi.models import RawPoll
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.datamodel import BundElectionPoll, PartyResult
from pollingapi.scraper.scraper_insertion import poll_to_raw_dict
from pollingapi.scraper.snapshots import save_html_snapshot


# TODO: Implement all classes
class VerianBaseScraper:
    URL: str = ""
    WORKER: str = ""
    STATE: str = "Bund"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
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


class VerianCurrentScraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid.htm"
    STATE: str = "Bund"
    WORKER = "verian_current"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2013Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2013.htm"
    STATE: str = "Bund"
    WORKER = "verian_2013"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2008Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2008.htm"
    STATE: str = "Bund"
    WORKER = "verian_2008"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2007Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2007.htm"
    STATE: str = "Bund"
    WORKER = "verian_2008"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2006Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2006.htm"
    STATE: str = "Bund"
    WORKER = "verian_2006"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2005Total(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2005.htm"
    STATE: str = "Bund"
    WORKER = "verian_2005"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2005Ost(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2005o.htm"
    STATE: str = "Ost"
    WORKER = "verian_2005_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2005West(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2005w.htm"
    STATE: str = "Ost"
    WORKER = "verian_2005_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2004Total(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2004.htm"
    STATE: str = "Bund"
    WORKER = "verian_2004"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2004Ost(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2004o.htm"
    STATE: str = "Ost"
    WORKER = "verian_2004_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2004West(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2004w.htm"
    STATE: str = "Ost"
    WORKER = "verian_2004_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2003Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2003.htm"
    STATE: str = "Bund"
    WORKER = "verian_2003"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2002Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2002.htm"
    STATE: str = "Bund"
    WORKER = "verian_2002"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2001Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2001.htm"
    STATE: str = "Bund"
    WORKER = "verian_2001"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian2000Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/2000.htm"
    STATE: str = "Bund"
    WORKER = "verian_2000"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian1999Scraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/1999.htm"
    STATE: str = "Bund"
    WORKER = "verian_1999"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian1998Total(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/1998.htm"
    STATE: str = "Bund"
    WORKER = "verian_1998"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian1998Ost(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/1998o.htm"
    STATE: str = "Ost"
    WORKER = "verian_1998_ost"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}


class Verian1998West(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid/1998w.htm"
    STATE: str = "Ost"
    WORKER = "verian_1998_west"
    SCOPE: str = "Bundestagswahl"
    INSTITUTE: str = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE: str = "wahlrecht.de"
    REQUEST_DELAY: float = 1.0
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}
