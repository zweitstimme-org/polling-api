"""Respondents transformation utilities."""

import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

from pollingapi.scraper.datamodel import SurveyMethod


@dataclass
class RespondentParseResult:
    """Result of parsing respondents field."""

    count: int | None = None
    method_hint: str | None = None
    date_range: str | None = None
    method: SurveyMethod | None = None
    date_start: str | None = None
    date_end: str | None = None
    parse_error: str | None = None


def normalize_respondents(respondents_str: str) -> int | None:
    """Extract numeric respondent count from string.

    Args:
        respondents_str: String containing respondent count

    Returns:
        Numeric count or None
    """
    if not respondents_str:
        return None

    s = str(respondents_str)

    # Extract number (handle German format: 1.234)
    match = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)", s)
    if match:
        count_str = match.group(1).replace(".", "")
        try:
            return int(count_str)
        except ValueError:
            pass

    return None


def _to_iso(day_month: str, year: str) -> str | None:
    with suppress(ValueError):
        return datetime.strptime(day_month + year, "%d.%m.%Y").date().isoformat()
    return None


def _publish_year(publish_date: str | None) -> str:
    if not publish_date:
        return ""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        with suppress(ValueError):
            return str(datetime.strptime(publish_date, fmt).year)
    return ""


def parse_respondents(
    respondents_str: str | None,
    publish_date: str | None = None,
) -> RespondentParseResult:
    """Parse respondents field for count, method, and dates.

    Args:
        respondents_str: Raw respondents field

    Returns:
        Parsed result with count, method hint, date range, and diagnostics
    """
    if not respondents_str:
        return RespondentParseResult(parse_error="Empty or invalid input")

    s = str(respondents_str)
    original = s

    # Extract method from prefix (e.g., "O • 2.004" or "TOM • 1.202")
    method_hint = None
    method = None
    method_prefix_match = re.match(r"^([A-Za-z]+)\s*[•·]\s*", s)
    if method_prefix_match:
        method_prefix = method_prefix_match.group(1).upper()
        if method_prefix == "O":
            method = SurveyMethod.ONLINE
        elif method_prefix in ("TOM", "TO"):
            method = SurveyMethod.TELEFON_ONLINE
        # Remove prefix from string for further processing
        s = s[method_prefix_match.end() :]

    # Extract count
    count = normalize_respondents(s)

    # Detect method from remaining text (if not already detected)
    if not method:
        s_lower = s.lower()
        if "telefon" in s_lower or "cati" in s_lower:
            method = SurveyMethod.TELEFONISCH
        elif "online" in s_lower or "cawi" in s_lower or "panel" in s_lower:
            method = SurveyMethod.ONLINE
        elif (
            "persönlich" in s_lower
            or "persoenlich" in s_lower
            or "face" in s_lower
            or "f2f" in s_lower
        ):
            method = SurveyMethod.PERSOENLICH
        elif "tom" in s_lower or "mixed" in s_lower or "komb" in s_lower:
            method = SurveyMethod.TELEFON_ONLINE

    method_hint = method.value if method else None

    # Extract embedded date range
    date_range = None
    date_start = None
    date_end = None
    date_match = re.search(r"(\d{1,2}\.\d{1,2}\.)\s*[–\-]\s*(\d{1,2}\.\d{1,2}\.)", s)
    if date_match:
        date_range = date_match.group(0)
        year = _publish_year(publish_date)
        date_start = _to_iso(date_match.group(1), year)
        date_end = _to_iso(date_match.group(2), year)

    missing = [
        name
        for name, value in (
            ("count", count),
            ("method", method),
        )
        if value is None
    ]
    parse_error = f"Could not extract {', '.join(missing)} from {original!r}" if missing else None

    return RespondentParseResult(
        count=count,
        method_hint=method_hint,
        date_range=date_range,
        method=method,
        date_start=date_start,
        date_end=date_end,
        parse_error=parse_error,
    )
