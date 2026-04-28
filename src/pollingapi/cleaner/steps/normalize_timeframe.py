"""Timeframe normalization using dateparser."""

import re
from dataclasses import dataclass
from enum import Enum, auto

import dateparser
import pandas as pd


class TimeframeResultType(Enum):
    """Classification of timeframe parsing results."""

    VALID_RANGE = auto()  # Normal date range with start and end
    SINGLE_DATE = auto()  # Only start date (single date like "30.06.")
    BIS_PREFIX = auto()  # "bis" prefix - both dates empty
    ELECTION_MARKER = auto()  # Election day marker - row should be ignored
    TIME_RANGE = auto()  # Time range (not dates) - row should be ignored
    UNKNOWN_DATE = auto()  # Question marks - row should be ignored
    INVALID = auto()  # Could not parse


@dataclass
class TimeframeParseResult:
    """Result of parsing a timeframe string."""

    start_date: str | None = None
    end_date: str | None = None
    result_type: TimeframeResultType = TimeframeResultType.INVALID
    original: str = ""

    @property
    def should_ignore_row(self) -> bool:
        """Check if this row should be ignored/skipped."""
        return self.result_type in (
            TimeframeResultType.ELECTION_MARKER,
            TimeframeResultType.TIME_RANGE,
            TimeframeResultType.UNKNOWN_DATE,
        )

    @property
    def is_bis_prefix(self) -> bool:
        """Check if this is a 'bis' prefix result."""
        return self.result_type == TimeframeResultType.BIS_PREFIX

    @property
    def is_single_date(self) -> bool:
        """Check if this is a single date result."""
        return self.result_type == TimeframeResultType.SINGLE_DATE


def parse_timeframe(timeframe_str: str, default_year: int | None = None) -> TimeframeParseResult:
    """Parse German timeframe string into start and end dates.

    Handles various German date formats and special cases:
    - Date ranges: "24.06.-26.06.2024", "01.–05.03.2024", "01.03.2024 - 05.03.2024"
    - Single dates without year: "30.06." (uses default_year for start date only)
    - Date ranges without year: "09.12.–13.12." (uses default_year)
    - "bis" prefix: "bis 31.08." (leaves both dates empty)
    - Election markers: "Bundestagswahl", "Europawahl" (marks for row ignore)
    - Time ranges: "20:15-22:00 Uhr" (marks for row ignore)
    - Unknown dates: "??.09.–??.09." (marks for row ignore)

    Args:
        timeframe_str: The timeframe string to parse
        default_year: Optional year to use when not in the string (typically from publish_date)

    Returns:
        TimeframeParseResult containing parsed dates and result classification
    """
    result = TimeframeParseResult(original=timeframe_str or "")

    if not timeframe_str or pd.isna(timeframe_str):
        result.result_type = TimeframeResultType.INVALID
        return result

    s = str(timeframe_str).strip()

    # Skip time ranges (election night exit polls like "20:15-22:00 Uhr")
    if re.search(r"\d{1,2}:\d{2}", s) and "Uhr" in s:
        result.result_type = TimeframeResultType.TIME_RANGE
        return result

    # Skip dates with question marks (unknown dates like "??.09.–??.09.")
    if "??" in s or "?" in s:
        result.result_type = TimeframeResultType.UNKNOWN_DATE
        return result

    # Check for election markers (case insensitive)
    election_markers = ["bundestagswahl", "europawahl", "landtagswahl"]
    s_lower = s.lower()
    if any(marker in s_lower for marker in election_markers):
        result.result_type = TimeframeResultType.ELECTION_MARKER
        return result

    settings = {
        "DATE_ORDER": "DMY",
        "PREFER_DAY_OF_MONTH": "first",
    }

    # Pattern A: Both dates have day.month.year (e.g., "24.06.-26.06.2024")
    # Groups: start_day, start_month, end_day, end_month, year
    pattern_a = r"(\d{1,2})\.(\d{1,2})\.[–\-]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})"
    match_a = re.search(pattern_a, s)
    if match_a:
        start_day, start_month, end_day, end_month, year = match_a.groups()
        start_str = f"{start_day}.{start_month}.{year}"
        end_str = f"{end_day}.{end_month}.{year}"

        start = dateparser.parse(start_str, settings=settings)
        end = dateparser.parse(end_str, settings=settings)

        if start and end:
            result.start_date = start.strftime("%Y-%m-%d")
            result.end_date = end.strftime("%Y-%m-%d")
            result.result_type = TimeframeResultType.VALID_RANGE
            return result

    # Pattern B: Only second date has day.month (e.g., "01.–05.03.2024")
    # Groups: start_day, end_day, month, year
    pattern_b = r"(\d{1,2})\.?[–\-]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})"
    match_b = re.search(pattern_b, s)
    if match_b:
        start_day, end_day, month, year = match_b.groups()
        start_str = f"{start_day}.{month}.{year}"
        end_str = f"{end_day}.{month}.{year}"

        start = dateparser.parse(start_str, settings=settings)
        end = dateparser.parse(end_str, settings=settings)

        if start and end:
            result.start_date = start.strftime("%Y-%m-%d")
            result.end_date = end.strftime("%Y-%m-%d")
            result.result_type = TimeframeResultType.VALID_RANGE
            return result

    # Pattern C: Full dates with spaces (e.g., "01.03.2024 - 05.03.2024")
    # Groups: start_day, start_month, start_year, end_day, end_month, end_year
    pattern_c = r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*[-–]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})"
    match_c = re.search(pattern_c, s)
    if match_c:
        start_day, start_month, start_year, end_day, end_month, end_year = match_c.groups()
        start_str = f"{start_day}.{start_month}.{start_year}"
        end_str = f"{end_day}.{end_month}.{end_year}"

        start = dateparser.parse(start_str, settings=settings)
        end = dateparser.parse(end_str, settings=settings)

        if start and end:
            result.start_date = start.strftime("%Y-%m-%d")
            result.end_date = end.strftime("%Y-%m-%d")
            result.result_type = TimeframeResultType.VALID_RANGE
            return result

    # Handle cases where default_year is available
    if default_year:
        # Pattern D: Dates without year (e.g., "09.12.–13.12.")
        # Groups: start_day, start_month, end_day, end_month
        pattern_d = r"(\d{1,2})\.(\d{1,2})\.?[–\-]\s*(\d{1,2})\.(\d{1,2})\.?"
        match_d = re.search(pattern_d, s)
        if match_d:
            start_day, start_month, end_day, end_month = match_d.groups()
            start_str = f"{start_day}.{start_month}.{default_year}"
            end_str = f"{end_day}.{end_month}.{default_year}"

            start = dateparser.parse(start_str, settings=settings)
            end = dateparser.parse(end_str, settings=settings)

            if start and end:
                result.start_date = start.strftime("%Y-%m-%d")
                result.end_date = end.strftime("%Y-%m-%d")
                result.result_type = TimeframeResultType.VALID_RANGE
                return result

        # Pattern E: "bis" prefix - only end date (e.g., "bis 31.08.")
        # Groups: end_day, end_month
        pattern_e = r"^bis\s+(\d{1,2})\.(\d{1,2})\.?$"
        match_e = re.search(pattern_e, s, re.IGNORECASE)
        if match_e:
            # For "bis" prefix: leave both dates empty
            result.result_type = TimeframeResultType.BIS_PREFIX
            return result

        # Pattern F: Single date without year (e.g., "30.06.", "09.02.")
        # Groups: day, month
        pattern_f = r"^(\d{1,2})\.(\d{1,2})\.?$"
        match_f = re.search(pattern_f, s)
        if match_f:
            day, month = match_f.groups()
            date_str = f"{day}.{month}.{default_year}"

            parsed = dateparser.parse(date_str, settings=settings)

            if parsed:
                # Single date: only set start_date, leave end_date as None
                result.start_date = parsed.strftime("%Y-%m-%d")
                result.end_date = None
                result.result_type = TimeframeResultType.SINGLE_DATE
                return result

    result.result_type = TimeframeResultType.INVALID
    return result


def normalize_timeframe_step(df: pd.DataFrame) -> pd.DataFrame:
    """Extract survey dates from Zeitraum column."""
    df = df.copy()

    if "Zeitraum" in df.columns:
        parsed = df["Zeitraum"].apply(parse_timeframe)
        df["survey_date_start"] = parsed.apply(lambda x: x.start_date)
        df["survey_date_end"] = parsed.apply(lambda x: x.end_date)
        df["_timeframe_result_type"] = parsed.apply(lambda x: x.result_type.name)
        df["_should_ignore"] = parsed.apply(lambda x: x.should_ignore_row)

    return df
