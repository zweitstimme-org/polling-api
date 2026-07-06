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
        assert data["status"] in {"pass", "warn", "fail"}
        assert data["service"] == "pollingapi"
        assert data["version"] == expected_version
        assert data["release_id"] == expected_version
        assert "time" in data
        assert "total_polls" in data
        assert "time_since_last_run_seconds" in data
        assert "checks" in data
        assert "database:polls" in data["checks"]
        assert "pipeline:last_run" in data["checks"]
        assert "validation:quality" in data["checks"]

    def test_heartbeat_alias(self, client):
        """Test heartbeat alias endpoint returns status."""
        response = client.get("/heartbeat")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"pass", "warn", "fail"}


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

    def test_list_polls_research_payload(self, client):
        """Test cleaned polls expose traceable normalized metadata."""
        response = client.get("/v1/polls?limit=1")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["public_id"].startswith("C")
        assert item["raw_public_id"].startswith("R")
        assert "institute_key" in item
        assert "election_key" in item
        assert item["results"]
        assert "party_key" in item["results"][0]
        assert "party_short_name" in item["results"][0]
        assert "matching_poll_id" in item
        assert "matching_poll_public_id" in item
        assert "matching_status" in item

    def test_list_polls_rejects_invalid_date_range(self, client):
        """Test list polls validates date ranges."""
        response = client.get("/v1/polls?date_from=2025-01-01&date_to=2024-01-01")
        assert response.status_code == 400

    def test_get_poll_by_public_id(self, client):
        """Test single poll lookup by public id."""
        public_id = client.get("/v1/polls?limit=1").json()["items"][0]["public_id"]
        response = client.get(f"/v1/polls/{public_id}")
        assert response.status_code == 200
        assert response.json()["public_id"] == public_id

    def test_get_poll_results(self, client):
        """Test single poll result lookup."""
        public_id = client.get("/v1/polls?limit=1").json()["items"][0]["public_id"]
        response = client.get(f"/v1/polls/{public_id}/results")
        assert response.status_code == 200
        results = response.json()
        assert results
        assert {"party_key", "party_short_name", "percentage"} <= results[0].keys()

    def test_list_polls_wide(self, client):
        """Test wide poll rows expose party percentages by party key."""
        response = client.get("/v1/polls/wide?limit=1")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["public_id"].startswith("C")
        assert isinstance(item["results"], dict)
        assert item["results"]


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

    def test_get_raw_poll_by_public_id(self, client):
        """Test raw poll lookup by public id."""
        public_id = client.get("/v1/raw-polls?limit=1").json()["items"][0]["public_id"]
        response = client.get(f"/v1/raw-polls/{public_id}")
        assert response.status_code == 200
        assert response.json()["public_id"] == public_id


class TestResultsEndpoints:
    """Tests for results API endpoints."""

    def test_list_observations(self, client):
        """Test observations endpoint returns long-format analysis rows."""
        response = client.get("/v1/observations?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert data["items"]
        item = data["items"][0]
        assert item["poll_public_id"].startswith("C")
        assert item["raw_public_id"].startswith("R")
        assert {"party_key", "party_short_name", "percentage"} <= item.keys()

    def test_list_results_alias(self, client):
        """Test results alias returns observation payload."""
        response = client.get("/v1/results")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data

    def test_list_results_with_party_filter(self, client):
        """Test list results accepts party key filter."""
        response = client.get("/v1/results?party_key=CDU_CSU")
        assert response.status_code == 200
        items = response.json()["items"]
        assert items
        assert {item["party_key"] for item in items} == {"CDU_CSU"}


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
        parties = response.json()
        assert parties
        assert {"key", "name", "short_name"} <= parties[0].keys()

    def test_get_methods(self, client):
        """Test get methods endpoint."""
        response = client.get("/v1/reference/methods")
        assert response.status_code == 200

    def test_get_elections(self, client):
        """Test get elections endpoint."""
        response = client.get("/v1/reference/elections")
        assert response.status_code == 200


class TestValidationEndpoints:
    """Tests for validation report endpoints."""

    def test_get_validation_report(self, client):
        """Test validation report endpoint returns aggregate payload."""
        response = client.get("/v1/validation/report")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in {"pass", "warn", "fail"}
        assert "checks" in data
        assert "top_failure_checks" in data
