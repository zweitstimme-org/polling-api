"""Tests for respondents parsing."""


from pollingapi.cleaner.transforms.respondents import parse_respondents


class TestParseRespondents:
    """Tests for parse_respondents function."""

    def test_online_prefix(self):
        """Test parsing O • prefix for Online method."""
        result = parse_respondents("O • 2.004")
        assert result.count == 2004
        assert result.method_hint == "Online"

    def test_tom_prefix(self):
        """Test parsing TOM • prefix for Telefon & Online method."""
        result = parse_respondents("TOM • 1.202")
        assert result.count == 1202
        assert result.method_hint == "Telefon & Online"

    def test_to_prefix(self):
        """Test parsing TO • prefix for Telefon & Online method."""
        result = parse_respondents("TO • 1.204")
        assert result.count == 1204
        assert result.method_hint == "Telefon & Online"

    def test_only_count(self):
        """Test parsing plain number without method."""
        result = parse_respondents("2.503")
        assert result.count == 2503
        assert result.method_hint is None

    def test_telefonisch_text(self):
        """Test detecting telefonisch method from text."""
        result = parse_respondents("telefonisch 1000")
        assert result.count == 1000
        assert result.method_hint == "Telefonisch"

    def test_online_text(self):
        """Test detecting Online method from text."""
        result = parse_respondents("Online-Panel 500")
        assert result.count == 500
        assert result.method_hint == "Online"

    def test_german_thousand_separator(self):
        """Test German thousand separator (. in numbers)."""
        result = parse_respondents("1.234")
        assert result.count == 1234

    def test_empty_string(self):
        """Test empty string returns None values."""
        result = parse_respondents("")
        assert result.count is None
        assert result.method_hint is None
        assert result.date_range is None

    def test_none_input(self):
        """Test None input returns None values."""
        result = parse_respondents(None)
        assert result.count is None
        assert result.method_hint is None
        assert result.date_range is None

    def test_embedded_date_range_after_count(self):
        """Test parsing concatenated count and date range from scraper output."""
        result = parse_respondents("TOM • 1.00325.02.–03.03.", "03.03.2026")
        assert result.count == 1003
        assert result.method_hint == "Telefon & Online"
        assert result.date_start == "2026-02-25"
        assert result.date_end == "2026-03-03"
