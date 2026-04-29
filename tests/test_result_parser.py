"""Tests for canonical party result parsing."""

import json

from pollingapi.cleaner.transforms.results import parse_party_results, parse_percentage
from pollingapi.scraper.datamodel import Party


class TestParsePercentage:
    """Tests for percentage value parsing."""

    def test_decimal_comma(self):
        assert parse_percentage("16,5 %") == 16.5

    def test_range_uses_midpoint(self):
        assert parse_percentage("5–7") == 6.0

    def test_placeholder_returns_none(self):
        assert parse_percentage("–") is None


class TestParsePartyResults:
    """Tests for raw parties JSON parsing."""

    def test_known_party_names(self):
        payload = json.dumps({"CDU/CSU": "32,1", "SPD": "16,5", "Grüne": "13"})

        result = parse_party_results(payload)

        assert result.parse_error is None
        assert [(entry.party, entry.value) for entry in result.valid_entries] == [
            (Party.CDU_CSU, 32.1),
            (Party.SPD, 16.5),
            (Party.GRUENE, 13.0),
        ]

    def test_metadata_columns_are_skipped(self):
        payload = json.dumps({"SPD": "16", "Summe": "100", "Quelle": "Forsa"})

        result = parse_party_results(payload)

        assert result.skipped == ["Summe", "Quelle"]
        assert len(result.party_results) == 1

    def test_unknown_party_is_reported_not_promoted(self):
        payload = json.dumps({"Unbekannt XYZ": "2"})

        result = parse_party_results(payload)

        assert result.party_results == []
        assert result.failed_entries[0].parse_error == "Unknown party name: 'Unbekannt XYZ'"
