"""Tests for timeframe normalization."""

import pytest

from pollingapi.cleaner.steps.normalize_timeframe import parse_timeframe


class TestParseTimeframe:
    """Tests for parse_timeframe function."""

    def test_pattern_a_both_dates_with_month(self):
        """Test Pattern A: Both dates have day.month."""
        start, end = parse_timeframe("24.06.-26.06.2024")
        assert start == "2024-06-24"
        assert end == "2024-06-26"

    def test_pattern_b_only_end_has_month(self):
        """Test Pattern B: Only end date has month."""
        start, end = parse_timeframe("01.–05.03.2024")
        assert start == "2024-03-01"
        assert end == "2024-03-05"

    def test_pattern_c_full_dates_with_spaces(self):
        """Test Pattern C: Full dates with spaces."""
        start, end = parse_timeframe("01.03.2024 - 05.03.2024")
        assert start == "2024-03-01"
        assert end == "2024-03-05"

    def test_pattern_d_without_year(self):
        """Test Pattern D: Dates without year uses default_year."""
        start, end = parse_timeframe("09.12.–13.12.", default_year=2024)
        assert start == "2024-12-09"
        assert end == "2024-12-13"

    def test_empty_string(self):
        """Test empty string returns None."""
        start, end = parse_timeframe("")
        assert start is None
        assert end is None

    def test_none_input(self):
        """Test None returns None."""
        start, end = parse_timeframe(None)
        assert start is None
        assert end is None

    def test_invalid_format(self):
        """Test invalid format returns None."""
        start, end = parse_timeframe("invalid")
        assert start is None
        assert end is None

    def test_with_dash_separator(self):
        """Test with dash separator instead of en-dash."""
        start, end = parse_timeframe("01.-05.03.2024")
        assert start == "2024-03-01"
        assert end == "2024-03-05"

    def test_pattern_d_without_default_year(self):
        """Test Pattern D without default year returns None."""
        start, end = parse_timeframe("09.12.–13.12.")
        assert start is None
        assert end is None
