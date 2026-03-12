"""Tests for API endpoints."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from pollingapi.main import app


@pytest.fixture
def client():
    """Create test client without lifespan events."""
    with (
        patch("pollingapi.main.init_db_async", return_value=None),
        TestClient(app, raise_server_exceptions=False) as test_client,
    ):
        yield test_client


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["message"] == "Zweitstimme Polling API"

    def test_root_includes_endpoints(self, client):
        """Test root endpoint lists available endpoints."""
        response = client.get("/")
        data = response.json()
        assert "endpoints" in data
        assert "/v1/polls" in data["endpoints"]


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns heartbeat payload."""
        expected_version = (
            (Path(__file__).resolve().parents[1] / ".apiversion")
            .read_text(encoding="utf-8")
            .strip()
        )

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"pass", "warn"}
        assert data["service"] == "pollingapi"
        assert data["version"] == expected_version
        assert data["release_id"] == expected_version
        assert "time" in data
        assert "total_polls" in data
        assert "time_since_last_run_seconds" in data
        assert "checks" in data
        assert "database:polls" in data["checks"]
        assert "pipeline:last_run" in data["checks"]

    def test_heartbeat_alias(self, client):
        """Test heartbeat alias endpoint returns status."""
        response = client.get("/heartbeat")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"pass", "warn"}


class TestPollsEndpoints:
    """Tests for polls API endpoints."""

    def test_list_polls_returns_data(self, client):
        """Test list polls returns data when present."""
        response = client.get("/v1/polls")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert data["meta"]["total"] > 0

    def test_list_polls_with_limit(self, client):
        """Test list polls respects limit parameter."""
        response = client.get("/v1/polls?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["limit"] == 10

    def test_list_polls_with_offset(self, client):
        """Test list polls respects offset parameter."""
        response = client.get("/v1/polls?offset=10")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["offset"] == 10

    def test_list_polls_with_scope_filter(self, client):
        """Test list polls accepts scope filter."""
        response = client.get("/v1/polls?scope=federal")
        assert response.status_code == 200

    def test_list_polls_with_date_filters(self, client):
        """Test list polls accepts date filters."""
        response = client.get("/v1/polls?date_from=2024-01-01&date_to=2024-12-31")
        assert response.status_code == 200


class TestRawPollsEndpoints:
    """Tests for raw polls API endpoints."""

    def test_list_raw_polls_returns_data(self, client):
        """Test list raw polls returns data when present."""
        response = client.get("/v1/raw-polls")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert data["meta"]["total"] > 0

    def test_list_raw_polls_with_limit(self, client):
        """Test list raw polls respects limit parameter."""
        response = client.get("/v1/raw-polls?limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["limit"] == 50


class TestResultsEndpoints:
    """Tests for results API endpoints."""

    def test_list_results_empty(self, client):
        """Test list results returns empty when no data."""
        response = client.get("/v1/results")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data

    def test_list_results_with_party_filter(self, client):
        """Test list results accepts party_id filter."""
        response = client.get("/v1/results?party_id=1")
        assert response.status_code == 200


class TestDictionariesEndpoints:
    """Tests for reference/dictionary endpoints."""

    def test_get_institutes(self, client):
        """Test get institutes endpoint."""
        response = client.get("/v1/reference/institutes")
        assert response.status_code == 200

    def test_get_parties(self, client):
        """Test get parties endpoint."""
        response = client.get("/v1/reference/parties")
        assert response.status_code == 200

    def test_get_methods(self, client):
        """Test get methods endpoint."""
        response = client.get("/v1/reference/methods")
        assert response.status_code == 200

    def test_get_elections(self, client):
        """Test get elections endpoint."""
        response = client.get("/v1/reference/elections")
        assert response.status_code == 200
