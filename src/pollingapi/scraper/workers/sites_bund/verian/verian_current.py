from bs4 import BeautifulSoup

from pollingapi.scraper.datamodel import BundElectionPoll, PartyResult
from pollingapi.scraper.workers.sites_bund.verian.base import VerianBaseScraper


class VerianCurrentScraper(VerianBaseScraper):
    URL = "https://www.wahlrecht.de/umfragen/emnid.htm"
    WORKER = "verian_current"
    STATE = "Bund"
    SCOPE = "Bundestagswahl"
    INSTITUTE = "Verian (Kantar Public, Emnid)"
    DATA_SOURCE = "wahlrecht.de"
    META_KEYS = {"Institut", "Auftraggeber", "Befragte", "Datum", "Zeitraum"}

    @staticmethod
    def _normalize_text(value: str) -> str:
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
        parties = []
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

            raw_headers = self._extract_headers(table)
            if not raw_headers:
                self.logger.debug(f"Table {table_idx} has no headers, skipping.")
                continue

            rows = table.select("tbody tr")
            if not rows:
                rows = table.find_all("tr")[1:]

            for row_idx, tr in enumerate(rows):
                row_data = self._extract_row_data(raw_headers, tr)
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
