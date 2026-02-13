"""Tests for method mapping."""

import pytest

from pollingapi.cleaner.json_mappings import map_method


class TestMapMethod:
    """Tests for map_method function."""

    def test_online(self):
        """Test mapping Online."""
        assert map_method("Online") == 3

    def test_telefonisch(self):
        """Test mapping Telefonisch."""
        assert map_method("Telefonisch") == 1

    def test_telefon_online(self):
        """Test mapping Telefon & Online."""
        assert map_method("Telefon & Online") == 4
        assert map_method("TOM") == 4

    def test_persoenlich(self):
        """Test mapping Persönlich."""
        assert map_method("Persönlich") == 2

    def test_unknown_returns_none(self):
        """Test that unknown method returns None (not 0)."""
        assert map_method("xyz") is None
        assert map_method("") is None
        assert map_method(None) is None

    def test_partial_match(self):
        """Test partial matching."""
        assert map_method("Online-Panel") == 3
        assert map_method("telefonisch befragung") == 1
