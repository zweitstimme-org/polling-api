"""Tests for date transformations."""

from datetime import date

import pytest

from pollingapi.cleaner.transforms.dates import (
    normalize_publish_date,
    normalize_survey_dates,
)


class TestNormalizePublishDate:
    """Tests for normalize_publish_date function."""

    def test_iso_format(self):
        """Test ISO format date."""
        assert normalize_publish_date("2024-01-15") == date(2024, 1, 15)

    def test_iso_format_with_time(self):
        """Test ISO format with time."""
        assert normalize_publish_date("2024-01-15T00:00:00") == date(2024, 1, 15)

    def test_iso_format_with_z(self):
        """Test ISO format with Z suffix."""
        assert normalize_publish_date("2024-01-15T00:00:00Z") == date(2024, 1, 15)

    def test_german_format_dmy(self):
        """Test German DMY format."""
        assert normalize_publish_date("15.01.2024") == date(2024, 1, 15)

    def test_german_format_with_month_name(self):
        """Test German format with month name."""
        result = normalize_publish_date("15. Januar 2024")
        assert result == date(2024, 1, 15)

    def test_empty_string_returns_none(self):
        """Test empty string returns None."""
        assert normalize_publish_date("") is None

    def test_none_returns_none(self):
        """Test None returns None."""
        assert normalize_publish_date(None) is None

    def test_invalid_date_returns_none(self):
        """Test invalid date returns None."""
        assert normalize_publish_date("not-a-date") is None


class TestNormalizeSurveyDates:
    """Tests for normalize_survey_dates function."""

    def test_explicit_start_and_end(self):
        """Test with explicit start and end dates."""
        start, end = normalize_survey_dates(
            start_date_str="2024-01-10",
            end_date_str="2024-01-15",
        )
        assert start == date(2024, 1, 10)
        assert end == date(2024, 1, 15)

    def test_with_zeitraum(self):
        """Test with Zeitraum text."""
        start, end = normalize_survey_dates(
            start_date_str=None,
            end_date_str=None,
            zeitraum="01.–05.03.2024",
        )
        assert start == date(2024, 3, 1)
        assert end == date(2024, 3, 5)

    def test_with_zeitraum_german_format(self):
        """Test with Zeitraum in German format."""
        start, end = normalize_survey_dates(
            start_date_str=None,
            end_date_str=None,
            zeitraum="24.06.-26.06.2024",
        )
        assert start == date(2024, 6, 24)
        assert end == date(2024, 6, 26)

    def test_zeitraum_with_default_year(self):
        """Test Zeitraum without year uses default year."""
        start, end = normalize_survey_dates(
            start_date_str=None,
            end_date_str=None,
            zeitraum="09.12.–13.12.",
            publish_date=date(2024, 1, 1),
        )
        assert start == date(2024, 12, 9)
        assert end == date(2024, 12, 13)

    def test_explicit_dates_take_precedence(self):
        """Test explicit dates take precedence over Zeitraum."""
        start, end = normalize_survey_dates(
            start_date_str="2024-01-10",
            end_date_str="2024-01-15",
            zeitraum="01.–05.03.2024",
        )
        assert start == date(2024, 1, 10)
        assert end == date(2024, 1, 15)

    def test_empty_returns_none(self):
        """Test with empty inputs returns None."""
        start, end = normalize_survey_dates(
            start_date_str=None,
            end_date_str=None,
            zeitraum=None,
        )
        assert start is None
        assert end is None
