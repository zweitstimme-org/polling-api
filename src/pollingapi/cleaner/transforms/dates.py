"""Date transformation utilities."""

import re
from datetime import date, datetime

import dateparser


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

    def _has_explicit_year(value: str | None) -> bool:
        return bool(value and re.search(r"\b\d{4}\b", value))

    def _shift_year(value: date | None, years: int) -> date | None:
        if value is None:
            return None
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(month=2, day=28, year=value.year + years)

    def _fix_inferred_years(
        start: date | None,
        end: date | None,
        raw_zeitraum: str | None,
        reference: date | None,
    ) -> tuple[date | None, date | None]:
        if not reference or _has_explicit_year(raw_zeitraum):
            return start, end

        # Ranges like "27.12.–30.12." published in early January belong to
        # the previous year, not the following December.
        if end and end > reference:
            start = _shift_year(start, -1)
            end = _shift_year(end, -1)

        # Ranges crossing New Year ("30.12.–03.01.") should have start in the
        # previous year and end in the publish year.
        if start and end and start > end:
            start = _shift_year(start, -1)

        return start, end

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
            start_date, end_date = _fix_inferred_years(start_date, end_date, zeitraum, publish_date)
            return start_date, end_date, should_ignore

        # Normal date range
        if result.start_date and not start_date:
            start_date = normalize_publish_date(result.start_date)
        if result.end_date and not end_date:
            end_date = normalize_publish_date(result.end_date)

        start_date, end_date = _fix_inferred_years(start_date, end_date, zeitraum, publish_date)

    return start_date, end_date, should_ignore
