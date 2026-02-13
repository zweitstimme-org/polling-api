"""Timeframe normalization using dateparser."""

import re
from typing import Tuple

import dateparser
import pandas as pd


def parse_timeframe(
    timeframe_str: str, default_year: int | None = None
) -> Tuple[str | None, str | None]:
    """Parse German timeframe string into start and end dates.

    Examples:
        "24.06.-26.06.2024" -> ("2024-06-24", "2024-06-26")  (both dates have month)
        "01.–05.03.2024" -> ("2024-03-01", "2024-03-05")    (only end has month)
        "01.03.2024 - 05.03.2024" -> ("2024-03-01", "2024-03-05")
        "09.12.–13.12." -> uses default_year or returns None

    Args:
        timeframe_str: The timeframe string to parse
        default_year: Optional year to use when not in the string
    """
    if not timeframe_str or pd.isna(timeframe_str):
        return None, None

    s = str(timeframe_str).strip()

    settings = {
        "DATE_ORDER": "DMY",
        "PREFER_DAY_OF_MONTH": "first",
    }

    # Pattern A: Both dates have day.month (e.g., "24.06.-26.06.2024")
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
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

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
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

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
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # Pattern D: Dates without year (e.g., "09.12.–13.12.")
    # Need to use default_year or extract from context
    if default_year:
        pattern_d = r"(\d{1,2})\.(\d{1,2})\.?[–\-]\s*(\d{1,2})\.(\d{1,2})\.?"
        match_d = re.search(pattern_d, s)
        if match_d:
            start_day, start_month, end_day, end_month = match_d.groups()
            start_str = f"{start_day}.{start_month}.{default_year}"
            end_str = f"{end_day}.{end_month}.{default_year}"

            start = dateparser.parse(start_str, settings=settings)
            end = dateparser.parse(end_str, settings=settings)

            if start and end:
                return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    return None, None


def normalize_timeframe_step(df: pd.DataFrame) -> pd.DataFrame:
    """Extract survey dates from Zeitraum column."""
    df = df.copy()

    if "Zeitraum" in df.columns:
        parsed = df["Zeitraum"].apply(parse_timeframe)
        df["survey_date_start"] = parsed.apply(lambda x: x[0])
        df["survey_date_end"] = parsed.apply(lambda x: x[1])

    return df
