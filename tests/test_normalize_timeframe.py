"""Tests for timeframe normalization."""

from pollingapi.cleaner.steps.normalize_timeframe import (
    TimeframeResultType,
    parse_timeframe,
)


class TestParseTimeframe:
    """Tests for parse_timeframe function."""

    def test_pattern_a_both_dates_with_month(self):
        """Test Pattern A: Both dates have day.month."""
        result = parse_timeframe("24.06.-26.06.2024")
        assert result.start_date == "2024-06-24"
        assert result.end_date == "2024-06-26"
        assert result.result_type == TimeframeResultType.VALID_RANGE
        assert not result.should_ignore_row

    def test_pattern_b_only_end_has_month(self):
        """Test Pattern B: Only end date has month."""
        result = parse_timeframe("01.–05.03.2024")
        assert result.start_date == "2024-03-01"
        assert result.end_date == "2024-03-05"
        assert result.result_type == TimeframeResultType.VALID_RANGE

    def test_pattern_c_full_dates_with_spaces(self):
        """Test Pattern C: Full dates with spaces."""
        result = parse_timeframe("01.03.2024 - 05.03.2024")
        assert result.start_date == "2024-03-01"
        assert result.end_date == "2024-03-05"
        assert result.result_type == TimeframeResultType.VALID_RANGE

    def test_pattern_d_without_year(self):
        """Test Pattern D: Dates without year uses default_year."""
        result = parse_timeframe("09.12.–13.12.", default_year=2024)
        assert result.start_date == "2024-12-09"
        assert result.end_date == "2024-12-13"
        assert result.result_type == TimeframeResultType.VALID_RANGE

    def test_pattern_e_bis_prefix(self):
        """Test Pattern E: 'bis' prefix - leaves both dates empty."""
        result = parse_timeframe("bis 31.08.", default_year=2024)
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.BIS_PREFIX
        assert result.is_bis_prefix
        assert not result.should_ignore_row

    def test_pattern_f_single_date(self):
        """Test Pattern F: Single date without year - only sets start_date."""
        result = parse_timeframe("30.06.", default_year=2024)
        assert result.start_date == "2024-06-30"
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.SINGLE_DATE
        assert result.is_single_date

    def test_pattern_f_single_date_leading_zero(self):
        """Test Pattern F: Single date with leading zero month."""
        result = parse_timeframe("09.02.", default_year=2024)
        assert result.start_date == "2024-02-09"
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.SINGLE_DATE

    def test_time_ranges_ignored(self):
        """Test that time ranges like election night are marked for ignore."""
        result = parse_timeframe("20:15-22:00 Uhr", default_year=2024)
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.TIME_RANGE
        assert result.should_ignore_row

    def test_question_marks_ignored(self):
        """Test that dates with question marks are marked for ignore."""
        result = parse_timeframe("??.09.–??.09.", default_year=2024)
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.UNKNOWN_DATE
        assert result.should_ignore_row

    def test_election_markers_ignored(self):
        """Test election day markers are marked for ignore."""
        result = parse_timeframe("Bundestagswahl", default_year=2024)
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.ELECTION_MARKER
        assert result.should_ignore_row

    def test_europawahl_ignored(self):
        """Test Europawahl is marked for ignore."""
        result = parse_timeframe("Europawahl", default_year=2024)
        assert result.result_type == TimeframeResultType.ELECTION_MARKER
        assert result.should_ignore_row

    def test_landtagswahl_ignored(self):
        """Test Landtagswahl is marked for ignore."""
        result = parse_timeframe("Landtagswahl", default_year=2024)
        assert result.result_type == TimeframeResultType.ELECTION_MARKER
        assert result.should_ignore_row

    def test_empty_string(self):
        """Test empty string returns invalid."""
        result = parse_timeframe("")
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_none_input(self):
        """Test None returns invalid."""
        result = parse_timeframe(None)
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_invalid_format(self):
        """Test invalid format returns invalid."""
        result = parse_timeframe("invalid")
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_with_dash_separator(self):
        """Test with dash separator instead of en-dash."""
        result = parse_timeframe("01.-05.03.2024")
        assert result.start_date == "2024-03-01"
        assert result.end_date == "2024-03-05"
        assert result.result_type == TimeframeResultType.VALID_RANGE

    def test_pattern_d_without_default_year(self):
        """Test Pattern D without default year returns invalid."""
        result = parse_timeframe("09.12.–13.12.")
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_single_date_without_year_returns_invalid(self):
        """Test single date without default_year returns invalid."""
        result = parse_timeframe("30.06.")
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_bis_without_year_returns_invalid(self):
        """Test 'bis' prefix without default_year returns invalid."""
        result = parse_timeframe("bis 31.08.")
        assert result.start_date is None
        assert result.end_date is None
        assert result.result_type == TimeframeResultType.INVALID

    def test_cross_month_boundary(self):
        """Test dates that cross month boundary (e.g., 28.10.–01.11.)."""
        result = parse_timeframe("28.10.–01.11.", default_year=2024)
        assert result.start_date == "2024-10-28"
        assert result.end_date == "2024-11-01"
        assert result.result_type == TimeframeResultType.VALID_RANGE

    def test_original_value_preserved(self):
        """Test that original timeframe string is preserved in result."""
        result = parse_timeframe("24.06.-26.06.2024")
        assert result.original == "24.06.-26.06.2024"
