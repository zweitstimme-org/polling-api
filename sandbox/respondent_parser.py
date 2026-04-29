# %% Imports
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


# %% Method Enum
class RespondentMethod(StrEnum):
    ONLINE = "Online"
    TELEFONISCH = "Telefonisch"
    TELEFON_ONLINE = "Telefon & Online"
    PERSOENLICH = "Persönlich"
    UNBEKANNT = "99"


# %% String pre-check
@dataclass
class RespondentStrCheck:
    has_letters: bool
    has_digits: bool
    is_valid: bool

    @property
    def has_content(self) -> bool:
        return self.has_letters or self.has_digits


def check_respondent_str(respondents_str) -> RespondentStrCheck:
    """Check whether a respondent string contains letters and/or digits."""
    if not isinstance(respondents_str, str) or not respondents_str.strip():
        return RespondentStrCheck(has_letters=False, has_digits=False, is_valid=False)
    return RespondentStrCheck(
        has_letters=bool(re.search(r"[a-zA-Z]", respondents_str)),
        has_digits=bool(re.search(r"\d", respondents_str)),
        is_valid=True,
    )


# %% Parse result
@dataclass
class RespondentParseResult:
    """Structured result of parsing a respondents field."""

    count: int | None = None
    method: RespondentMethod | None = None
    date_start: str | None = None
    date_end: str | None = None
    parse_error: str | None = None

    @property
    def is_complete(self) -> bool:
        """True only if all expected fields were successfully extracted."""
        return all([self.count, self.method, self.date_start, self.date_end])


# %% Method resolution helpers
_METHOD_PREFIX_MAP: dict[str, RespondentMethod] = {
    "O": RespondentMethod.ONLINE,
    "T": RespondentMethod.TELEFONISCH,
    "TO": RespondentMethod.TELEFON_ONLINE,
    "TOM": RespondentMethod.TELEFON_ONLINE,
}

_METHOD_KEYWORD_MAP: list[tuple[tuple[str, ...], RespondentMethod]] = [
    (("telefon", "cati"), RespondentMethod.TELEFONISCH),
    (("online", "cawi", "panel"), RespondentMethod.ONLINE),
    (("persönlich", "persoenlich", "face", "f2f"), RespondentMethod.PERSOENLICH),
    (("tom", "mixed", "komb"), RespondentMethod.TELEFON_ONLINE),
]


def _method_from_keywords(s: str) -> RespondentMethod | None:
    s_lower = s.lower()
    for keywords, method in _METHOD_KEYWORD_MAP:
        if any(kw in s_lower for kw in keywords):
            return method
    return None


def _to_iso(day_month: str, year: str) -> str | None:
    """Convert 'DD.MM.' + 'YYYY' to ISO format 'YYYY-MM-DD'."""
    try:
        return datetime.strptime(day_month + year, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


# %% Core parser
def parse_respondents(
    respondents_str: str,
    publish_date: str | None = None,
) -> RespondentParseResult:
    """Parse a raw respondents string into count, method, and date range.

    Handles concatenated formats like "O • 1.00004.10.–11.10." where
    the count and date range are not separated by whitespace.

    Args:
        respondents_str: Raw value from the respondents column.
        publish_date: Optional publish date (DD.MM.YYYY) used to infer
                      the year for the extracted date range.
    Returns:
        RespondentParseResult — check .is_complete before writing to columns,
        and .parse_error for diagnostics on failure.
    """
    check = check_respondent_str(respondents_str)
    if not check.is_valid:
        return RespondentParseResult(parse_error="Empty or invalid input")
    if not check.has_digits:
        return RespondentParseResult(parse_error="No numeric content — cannot extract count")

    s = respondents_str.strip()
    method: RespondentMethod | None = None

    # --- Method prefix: "O •", "TOM •", etc. ---
    prefix_match = re.match(r"^([A-Za-z]+)\s*[•·]\s*", s)
    if prefix_match:
        method = _METHOD_PREFIX_MAP.get(prefix_match.group(1).upper())
        s = s[prefix_match.end() :]

    # Fall back to keyword scan if prefix gave nothing
    if not method:
        method = _method_from_keywords(s)

    # --- Respondent count (German thousands format: 1.234 → 1234) ---
    count: int | None = None
    count_match = re.match(r"(\d{1,3}(?:\.\d{3})+|\d+)", s)
    if count_match:
        count = int(count_match.group(1).replace(".", ""))
        s = s[count_match.end() :]

    # --- Date range: DD.MM.–DD.MM. ---
    date_start: str | None = None
    date_end: str | None = None
    date_match = re.search(r"(\d{2}\.\d{2}\.)\s*[–\-]\s*(\d{2}\.\d{2}\.)", s)
    if date_match:
        year = ""
        if publish_date:
            with suppress(ValueError):
                year = str(datetime.strptime(publish_date, "%d.%m.%Y").year)
        date_start = _to_iso(date_match.group(1), year)
        date_end = _to_iso(date_match.group(2), year)

    # --- Collect missing fields for error report ---
    missing = [
        name
        for name, val in [
            ("count", count),
            ("method", method),
            ("date_start", date_start),
            ("date_end", date_end),
        ]
        if not val
    ]
    parse_error = f"Could not extract: {', '.join(missing)}" if missing else None

    return RespondentParseResult(
        count=count,
        method=method,
        date_start=date_start,
        date_end=date_end,
        parse_error=parse_error,
    )


# %% Quick smoke test against example data
respondents_column = [
    "O • 1.00004.10.–11.10.",
    " O • 1.00110.11.–16.11.",
    "TOM • 1.00607.02.–12.02.",
    "TOM • 1.04601.09.–06.09.",
]
publish_dates = [
    "13.12.2023",
    "13.02.2013",
    "16.02.2014",
    "22.02.2014",
]

for raw, pub in zip(respondents_column, publish_dates, strict=True):
    result = parse_respondents(raw, publish_date=pub)
    print(result)
    print(f"  → complete: {result.is_complete}\n")
