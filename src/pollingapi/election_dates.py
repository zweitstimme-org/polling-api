"""Parse „Nächster Wahltermin“ strings from Wahlrecht.de Landtage overview.

Source: https://www.wahlrecht.de/umfragen/landtage/

Fixed dates (e.g. „8. März 2026“) are parsed as-is; seasonal terms (Herbst,
Frühjahr, Winter, Sommer) are converted to a representative mid-period date
and marked as estimated.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Tuple

# German month names (lowercase for matching)
_DE_MONTHS = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

# Seasonal term -> (month, day) for mid-period; all are estimated
_SEASONAL = {
    "winter": (1, 15),   # mid-January
    "frühjahr": (3, 15), # mid-March (spring)
    "sommer": (7, 15),   # mid-July
    "herbst": (10, 15),  # mid-October (autumn)
}


def parse_next_election_date(text: str) -> Tuple[date | None, bool]:
    """Parse a „Nächster Wahltermin“ string into a date and estimated flag.

    Args:
        text: Raw string from Wahlrecht (e.g. „8. März 2026“, „Herbst 2028“).

    Returns:
        (date, is_estimated): Parsed date or None if unparseable; is_estimated
        True for seasonal terms (Herbst, Frühjahr, Winter, Sommer), False for
        fixed day/month/year.
    """
    if not text or not isinstance(text, str):
        return (None, False)
    s = text.strip().replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s)
    if not s:
        return (None, False)

    # Fixed date: "8. März 2026", "20. September 2026"
    fixed_match = re.match(r"^(\d{1,2})\.\s*([a-zA-ZäöüÄÖÜß]+)\s+(\d{4})$", s)
    if fixed_match:
        day_s, month_s, year_s = fixed_match.groups()
        month_lower = month_s.lower()
        if month_lower in _DE_MONTHS:
            try:
                d = date(int(year_s), _DE_MONTHS[month_lower], int(day_s))
                return (d, False)
            except ValueError:
                pass

    # Seasonal: "Herbst 2028", "Frühjahr 2027", "Winter 2030"
    seasonal_match = re.match(r"^([a-zA-ZäöüÄÖÜß]+)\s+(\d{4})$", s)
    if seasonal_match:
        term, year_s = seasonal_match.groups()
        term_lower = term.lower()
        if term_lower in _SEASONAL:
            month, day = _SEASONAL[term_lower]
            try:
                d = date(int(year_s), month, day)
                return (d, True)
            except ValueError:
                pass

    return (None, False)
