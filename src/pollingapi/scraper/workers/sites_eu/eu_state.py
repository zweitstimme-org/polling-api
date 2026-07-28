"""Wahlrecht.de Europawahl state scraper."""

import re

from pollingapi.scraper.datamodel import BundElectionPoll, GermanState
from pollingapi.scraper.workers.sites_eu.eu_fed import EuFedCurrentScraper

STATE_BY_ID = {
    "bw": GermanState.BW,
    "by": GermanState.BY,
    "be": GermanState.BE,
    "bb": GermanState.BB,
    "hb": GermanState.HB,
    "hh": GermanState.HH,
    "he": GermanState.HE,
    "mv": GermanState.MV,
    "ni": GermanState.NI,
    "nw": GermanState.NW,
    "rp": GermanState.RP,
    "sl": GermanState.SL,
    "sn": GermanState.SN,
    "st": GermanState.ST,
    "sh": GermanState.SH,
    "th": GermanState.TH,
}


class EuStateCurrentScraper(EuFedCurrentScraper):
    WORKER = "eu_state"
    TABLES = (2,)

    def _respondents_and_zeitraum(self, cell) -> tuple[str, str]:
        lines = [
            re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
            for text in cell.get_text("\n", strip=True).splitlines()
        ]
        lines = [line for line in lines if line]
        if lines and re.search(r"(\d|\?)\d?\.\d|\?\?", lines[-1]):
            respondents = " ".join(lines[:-1])
            zeitraum = lines[-1]
        else:
            respondents = " ".join(lines)
            zeitraum = ""

        title = re.sub(r"\s+", " ", cell.get("title", "").replace("\xa0", " ")).strip()
        if title and title not in respondents:
            respondents = f"{respondents} {title}".strip()

        return respondents, zeitraum

    def _row_to_state_poll(self, cells, party_headers, state):
        if len(cells) < 5:
            return None

        institute_date = self._text(cells[0])
        match = re.search(r"\((\d{2}\.\d{2}\.\d{2,4})\)$", institute_date)
        if not match:
            return None

        parties = self._party_results(cells[4:], party_headers)
        if not parties:
            return None

        respondents, zeitraum = self._respondents_and_zeitraum(cells[2])

        return BundElectionPoll(
            data_source=self.DATA_SOURCE,
            worker=self.WORKER,
            scope=self.SCOPE,
            state=state,
            institut=institute_date[: match.start()].strip(),
            auftraggeber=self._text(cells[1]) or None,
            datum=match.group(1),
            befragte=respondents,
            zeitraum=zeitraum,
            results=parties,
        )

    def _parse_table(self, table):
        party_headers = self._party_headers(table)
        polls = []
        current_state = GermanState.BUND

        for row in table.select("tbody tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue

            state_header = row.find("th", class_="li", recursive=False)
            if state_header and state_header.get("id") in STATE_BY_ID:
                current_state = STATE_BY_ID[state_header["id"]]
                cells = cells[2:]

            poll = self._row_to_state_poll(cells, party_headers, current_state)
            if poll:
                polls.append(poll)

        return polls
