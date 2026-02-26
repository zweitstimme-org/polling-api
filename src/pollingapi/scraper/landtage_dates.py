"""Fetch „Nächster Wahltermin“ for each state from Wahlrecht.de Landtage overview.

Source: https://www.wahlrecht.de/umfragen/landtage/
Used to update Election.date and Election.date_is_estimated for state elections.
"""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

LANDTAGE_OVERVIEW_URL = "https://www.wahlrecht.de/umfragen/landtage/"


def fetch_landtage_next_election_dates() -> list[tuple[str, str]]:
    """Fetch the Landtage overview page and extract (scope, date_text) per state.

    The overview table has: state name (link to state page), then „Nächster
    Wahltermin“ (link text like „8. März 2026“ or „Herbst 2028“). Scope is
    derived from the state link href stem (e.g. baden-wuerttemberg.htm -> baden-wuerttemberg).

    Returns:
        List of (scope, raw_date_text). Scope matches our canonical scope
        (e.g. baden-wuerttemberg, bayern). Skips rows where scope or date
        cannot be determined.
    """
    resp = requests.get(LANDTAGE_OVERVIEW_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    out: list[tuple[str, str]] = []

    # Find main content table; state column is <th>, date column is <td>
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            # First cell: state link e.g. <a href="baden-wuerttemberg.htm">Baden-Württemberg</a>
            state_link = cells[0].find("a", href=True)
            if not state_link:
                continue
            href = state_link.get("href", "")
            # href can be "baden-wuerttemberg.htm" or relative
            stem = re.sub(r"\.htm(l?)$", "", href.strip().split("/")[-1])
            if not stem:
                continue
            scope = stem

            # Second cell: „Nächster Wahltermin“ – often a link with text like "8. März 2026" or "Herbst 2028"
            second_cell = cells[1]
            date_link = second_cell.find("a")
            if date_link:
                date_text = date_link.get_text(separator=" ", strip=True)
            else:
                date_text = second_cell.get_text(separator=" ", strip=True)
            # Normalize spaces and remove extra text (e.g. footnote refs)
            date_text = re.sub(r"\s+", " ", date_text).strip()
            if not date_text or date_text.lower().startswith("nächster"):
                continue
            out.append((scope, date_text))

    return out
