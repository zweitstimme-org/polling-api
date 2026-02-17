"""Tests for JSON mappings."""

import pytest

from pollingapi.cleaner.json_mappings import (
    get_party_short_name,
    map_institute,
    map_parliament,
    map_party,
    map_tasker,
)


class TestMapInstitute:
    """Tests for map_institute function."""

    def test_known_institute_forsa(self):
        """Test mapping Forsa institute."""
        result = map_institute("Forsa")
        assert result == 2

    def test_known_institute_insa(self):
        """Test mapping INSA institute."""
        result = map_institute("INSA")
        assert result == 5

    def test_known_institute_emnid(self):
        """Test mapping Emnid institute."""
        result = map_institute("Emnid")
        assert result == 3

    def test_unknown_institute_returns_99(self):
        """Test that unknown institute returns 99 (Unknown)."""
        assert map_institute("xyz") == 99
        assert map_institute("") == 99
        assert map_institute("Unknown Institute") == 99

    def test_partial_match(self):
        """Test partial matching."""
        result = map_institute("Forsa (emnid)")
        assert result == 2

    def test_case_insensitive(self):
        """Test case insensitive matching."""
        assert map_institute("forsa") == 2
        assert map_institute("INSA") == 5


class TestMapParty:
    """Tests for map_party function."""

    def test_cdu(self):
        """Test mapping CDU."""
        assert map_party("CDU") == 101

    def test_csu(self):
        """Test mapping CSU."""
        assert map_party("CSU") == 102

    def test_cdu_csu_variation(self):
        """Test mapping CDU/CSU variation."""
        assert map_party("CDU/CSU") == 1

    def test_union(self):
        """Test mapping Union."""
        assert map_party("Union") == 1

    def test_spd(self):
        """Test mapping SPD."""
        assert map_party("SPD") == 2

    def test_fdp(self):
        """Test mapping FDP."""
        assert map_party("FDP") == 3

    def test_gruene(self):
        """Test mapping Grüne."""
        assert map_party("Grüne") == 4
        assert map_party("Gruene") == 4
        assert map_party("Bündnis 90/Die Grünen") == 4

    def test_linke(self):
        """Test mapping Linke."""
        assert map_party("Die Linke") == 5
        assert map_party("Linke") == 5

    def test_afd(self):
        """Test mapping AfD."""
        assert map_party("AfD") == 7

    def test_fw(self):
        """Test mapping Freie Wähler."""
        assert map_party("Freie Wähler") == 8
        assert map_party("FW") == 8

    def test_unknown_returns_none(self):
        """Test that unknown party returns None."""
        assert map_party("xyz") is None
        assert map_party("") is None
        assert map_party(None) is None

    def test_by_full_name(self):
        """Test mapping by full party name."""
        assert map_party("Alternative für Deutschland") == 7


class TestMapParliament:
    """Tests for map_parliament function."""

    def test_federal(self):
        """Test mapping federal scope."""
        assert map_parliament("federal") == 0
        assert map_parliament("bundestag") == 0
        assert map_parliament("Bundestagswahl") == 0

    def test_bayern(self):
        """Test mapping Bayern scope."""
        assert map_parliament("bayern") == 2
        assert map_parliament("bavaria") == 2

    def test_berlin(self):
        """Test mapping Berlin scope."""
        assert map_parliament("berlin") == 3

    def test_eu(self):
        """Test mapping EU scope."""
        assert map_parliament("eu") == 17
        assert map_parliament("europawahl") == 17

    def test_landtagswahlen(self):
        """Test mapping various state elections."""
        assert map_parliament("brandenburg") == 4
        assert map_parliament("bremen") == 5
        assert map_parliament("hamburg") == 6
        assert map_parliament("hessen") == 7

    def test_unknown_returns_bundestag(self):
        """Test that unknown scope returns 0 (Bundestag)."""
        assert map_parliament("xyz") == 0
        assert map_parliament("") == 0

    def test_none_returns_bundestag(self):
        """Test that None returns 0 (Bundestag)."""
        assert map_parliament(None) == 0


class TestMapTasker:
    """Tests for map_tasker function."""

    def test_known_tasker(self):
        """Test mapping known tasker."""
        result = map_tasker("BILD")
        assert result is not None

    def test_unknown_returns_none(self):
        """Test that unknown tasker returns None."""
        assert map_tasker("xyz") is None
        assert map_tasker("") is None
        assert map_tasker(None) is None


class TestGetPartyShortName:
    """Tests for get_party_short_name function."""

    def test_cdu(self):
        """Test getting CDU short name."""
        assert get_party_short_name(101) == "CDU"

    def test_spd(self):
        """Test getting SPD short name."""
        assert get_party_short_name(2) == "SPD"

    def test_unknown_returns_none(self):
        """Test that unknown ID returns None."""
        assert get_party_short_name(999) is None
