"""Date transformation utilities."""

import re
from datetime import date, datetime

import dateparser


# Pattern for election/section headers from Wahlrecht: "Landtagswahl am 02.02.2003", "Europawahl am 09.06.2024"
_ELECTION_DATE_PATTERN = re.compile(
    r"\bam\s+(\d{1,2})\.(\d{1,2})\.(\d{4})\b",
    re.IGNORECASE,
)


def normalize_publish_date(date_str: str, fallback_year: int | None = None) -> date | None:
    """Parse publish date string to date object.

    Args:
        date_str: Date string to parse
        fallback_year: Year to use if not in date string

    Returns:
        Parsed date or None
    """
    if not date_str:
        return None

    raw = str(date_str).strip()

    # Fast-path common ISO formats from scrapers / DB.
    # Examples: 2026-01-31, 2026-01-31T00:00:00, 2026-01-31T00:00:00Z
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    # Wahlrecht section headers: "Landtagswahl am 02.02.2003", "Europawahl am 09.06.2024"
    match = _ELECTION_DATE_PATTERN.search(raw)
    if match:
        try:
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return date(year, month, day)
        except ValueError:
            pass

    settings = {
        "DATE_ORDER": "DMY",
        "PREFER_DAY_OF_MONTH": "first",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }

    parsed = dateparser.parse(raw, settings=settings)  # type: ignore[arg-type]
    if parsed:
        return parsed.date()

    return None


def normalize_survey_dates(
    start_date_str: str | None,
    end_date_str: str | None,
    zeitraum: str | None = None,
    publish_date: date | None = None,
) -> tuple[date | None, date | None, bool]:
    """Normalize survey start and end dates.

    Args:
        start_date_str: Survey start date string
        end_date_str: Survey end date string
        zeitraum: Zeitraum text (e.g., "01.–05.03.2024")
        publish_date: Publish date for fallback year

    Returns:
        Tuple of (start_date, end_date, should_ignore)
        should_ignore is True if the row should be skipped (election markers, etc.)
    """
    start_date = None
    end_date = None
    should_ignore = False

    # Parse explicit dates
    if start_date_str:
        start_date = normalize_publish_date(start_date_str)
    if end_date_str:
        end_date = normalize_publish_date(end_date_str)

    # Try parsing Zeitraum if dates not found
    if not (start_date and end_date) and zeitraum:
        from pollingapi.cleaner.steps.normalize_timeframe import parse_timeframe

        # Extract year from publish_date for parsing zeitraum without year
        default_year = publish_date.year if publish_date else None

        result = parse_timeframe(zeitraum, default_year=default_year)

        # Check if this row should be ignored
        if result.should_ignore_row:
            should_ignore = True
            return start_date, end_date, should_ignore

        # Handle bis prefix - leave both dates empty
        if result.is_bis_prefix:
            return None, None, should_ignore

        # Handle single date - only set start_date
        if result.is_single_date and result.start_date and not start_date:
            start_date = normalize_publish_date(result.start_date)
            # end_date remains None for single dates
            return start_date, end_date, should_ignore

        # Normal date range
        if result.start_date and not start_date:
            start_date = normalize_publish_date(result.start_date)
        if result.end_date and not end_date:
            end_date = normalize_publish_date(result.end_date)

    return start_date, end_date, should_ignore
