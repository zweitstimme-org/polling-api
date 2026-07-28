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


class TestReportEndpoint:
    """Tests for PDF report endpoint."""

    def test_report_serves_latest_pdf(self, client, tmp_path, monkeypatch):
        """Test report endpoint returns the latest generated PDF."""
        report_dir = tmp_path / "reports"
        report_dir.mkdir()
        (report_dir / "pollingapi-report-latest.pdf").write_bytes(b"%PDF-1.7\n")
        monkeypatch.setattr("pollingapi.core.settings.report_dir", report_dir)

        response = client.get("/report")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"].startswith("inline;")
        assert response.content.startswith(b"%PDF")


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


class TestV2Endpoints:
    """Tests for the v2 API surface."""

    def test_v2_polls_uses_standard_list_envelope(self, client):
        """Test v2 polls return data with pagination and links."""
        response = client.get("/v2/polls?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert {"data", "pagination", "links"} <= data.keys()
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["total"] > 0
        assert data["data"]

    def test_v2_poll_results_primary_name(self, client):
        """Test v2 exposes long-format results under poll-results."""
        response = client.get("/v2/poll-results?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert {"data", "pagination", "links"} <= data.keys()
        assert data["data"]
        assert {"poll_public_id", "party_key", "percentage"} <= data["data"][0].keys()

    def test_v2_datasets(self, client):
        """Test v2 dataset registry and explicit dataset poll endpoint."""
        response = client.get("/v2/datasets")
        assert response.status_code == 200
        datasets = response.json()
        assert {item["key"] for item in datasets} >= {"default", "all-cleaned"}

        response = client.get("/v2/datasets/default/polls?limit=1")
        assert response.status_code == 200
        assert response.json()["data"]

    def test_v2_reference_resource_names(self, client):
        """Test v2 promotes reference tables to English resource names."""
        for path in [
            "/v2/parties",
            "/v2/institutes",
            "/v2/providers",
            "/v2/survey-methods",
            "/v2/scopes",
            "/v2/commissioners",
            "/v2/reference-data",
        ]:
            response = client.get(path)
            assert response.status_code == 200

    def test_v2_downloads_index(self, client):
        """Test v2 downloads use plural resource naming."""
        response = client.get("/v2/downloads")
        assert response.status_code == 200
        filenames = {item["filename"] for item in response.json()}
        assert {"polls.json", "poll-results.csv", "raw-polls.parquet"} <= filenames

    def test_v2_archive_routes_are_well_formed(self, client):
        """Test v2 archive paths use slash-separated resource names."""
        route_paths = {route.path for route in client.app.routes}
        assert "/v2/archives/latest" in route_paths
        assert "/v2/archives/{filename}" in route_paths
        assert "/v2/archives/{filename}/download" in route_paths

    def test_openapi_shows_v2_but_hides_v1(self, client):
        """Test public OpenAPI docs show v2 while keeping v1 hidden."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/v2/polls" in paths
        assert "/v2/poll-results" in paths
        assert "/v1/polls" not in paths
        tags = {tag["name"] for tag in response.json()["tags"]}
        assert {"observations", "reference", "validation", "archive"}.isdisjoint(tags)
        assert {"poll-results", "reference-data", "validation-reports", "archives"} <= tags

        legacy_response = client.get("/v1/polls?limit=1")
        assert legacy_response.status_code == 200


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
