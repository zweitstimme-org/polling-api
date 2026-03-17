"""Fetch next Bundestag election date from Wahlrecht.de Termine page.

Source: https://www.wahlrecht.de/termine.htm

We extract the row where the columns indicate:
- Bundesland: "alle Bundesländer"
- Organ(e): "Bundestag"

The page separates the year (e.g. 2029) and the term/date (e.g. "Winter" or
"28. September") into different columns. We combine them into a single string
like "Winter 2029" so it can be parsed by `pollingapi.election_dates.parse_next_election_date`.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

TERMINE_URL = "https://www.wahlrecht.de/termine.htm"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def fetch_bundestag_next_election_date_text() -> str | None:
    """Fetch the Termine page and extract a parsable date text for Bundestag.

    Returns:
        A string like "Winter 2029" or "28. September 2025" (depending on what
        Wahlrecht publishes). Returns None if not found.
    """
    resp = requests.get(TERMINE_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Find a table row containing "alle Bundesländer" and "Bundestag"
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            texts = [_norm(c.get_text(separator=" ", strip=True)) for c in cells]
            joined = " | ".join(texts).lower()
            if "bundestag" not in joined:
                continue
            if "alle bundesländer" not in joined and "alle bundeslaender" not in joined:
                continue

            # Typical order: Year | Termin | Bundesland | Organ(e) | Wahlperiode
            year_text = texts[0]
            termin_text = texts[1]

            year_match = re.search(r"\b(\d{4})\b", year_text)
            year = year_match.group(1) if year_match else None
            termin_text = _norm(termin_text)

            if not termin_text:
                continue

            # If termin already contains a year, return as-is
            if re.search(r"\b\d{4}\b", termin_text):
                return termin_text

            # Otherwise combine with year (e.g. "Winter" + "2029" -> "Winter 2029")
            if year:
                return f"{termin_text} {year}"

            return termin_text

    return None

