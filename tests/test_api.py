"""Integration tests for FastAPI endpoints."""

from __future__ import annotations

import pathlib
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import (
    get_gateway_repository,
    get_prediction_service,
    get_telemetry_repository,
)
from src.core.ranker_3sigma import ThreeSigmaRanker
from src.data.repository import GatewayRepository, TelemetryRepository
from src.services.prediction_service import PredictionService


def test_health_endpoint(test_client: TestClient):
    """GET /health should return 200 with service status."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["ranker_algorithm"] == "ThreeSigmaRanker"
    assert "offline_duration_sec" in data["configured_metrics"]


def test_get_weekly_predictions_valid(test_client: TestClient):
    """GET /predictions/{week_start} with valid Monday returns 15 ranked recommendations."""
    response = test_client.get("/predictions/2026-02-02?limit=15")
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-02-02"
    assert data["total_dispatches"] == 15
    recs = data["recommendations"]
    assert len(recs) == 15
    assert recs[0]["rank"] == 1
    assert recs[0]["gateway_id"] == "0A0000000001"
    assert "reason" in recs[0]


def test_get_weekly_predictions_invalid_date_format(test_client: TestClient):
    """GET /predictions/{invalid_date} should return 422 Unprocessable Entity."""
    response = test_client.get("/predictions/not-a-date")
    assert response.status_code == 422
    assert "Invalid date format" in response.json()["detail"]


def test_get_weekly_predictions_non_monday(test_client: TestClient):
    """GET /predictions/{sunday_date} should return 400 Bad Request."""
    # 2026-02-01 was a Sunday
    response = test_client.get("/predictions/2026-02-01")
    assert response.status_code == 400
    assert "not a Monday" in response.json()["detail"]


def test_get_weekly_predictions_limit_bounds_validation(test_client: TestClient):
    """GET /predictions/{week_start}?limit=0 or limit=51 should return 422 validation error."""
    res_low = test_client.get("/predictions/2026-02-02?limit=0")
    assert res_low.status_code == 422

    res_high = test_client.get("/predictions/2026-02-02?limit=51")
    assert res_high.status_code == 422


def test_get_weekly_predictions_date_without_telemetry(test_client: TestClient):
    """GET /predictions/{monday} on a Monday with no recorded baseline telemetry returns 404."""
    # 2020-01-06 was a Monday, but far before synthetic telemetry range (2026)
    response = test_client.get("/predictions/2020-01-06")
    assert response.status_code == 404
    assert "No telemetry data found" in response.json()["detail"]


def test_explain_gateway_valid(test_client: TestClient):
    """GET /predictions/{week_start}/gateway/{id} returns drill-down stats."""
    response = test_client.get("/predictions/2026-02-02/gateway/0A0000000001")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == "0A0000000001"
    assert data["rank"] == 1
    assert len(data["metric_breakdown"]) == 3
    assert data["total_flagged_hours"] > 0


def test_explain_gateway_unknown(test_client: TestClient):
    """GET /predictions/{week_start}/gateway/{unknown} returns 404."""
    response = test_client.get("/predictions/2026-02-02/gateway/UNKNOWN_GW_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_gateways(test_client: TestClient):
    """GET /gateways returns master asset register."""
    response = test_client.get("/gateways")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_gateway_metadata_by_id(test_client: TestClient):
    """GET /gateways/{id} returns specific gateway metadata."""
    response = test_client.get("/gateways/0A0000000001")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == "0A0000000001"
    assert data["tenant"] == "Utility A"


def test_get_gateway_metadata_not_found(test_client: TestClient):
    """GET /gateways/{unknown} returns 404."""
    response = test_client.get("/gateways/UNKNOWN999")
    assert response.status_code == 404


def test_pipeline_run_invalid_date_in_weeks(test_client: TestClient):
    """POST /pipeline/run with invalid date in weeks returns 422."""
    response = test_client.post(
        "/pipeline/run",
        json={"weeks": ["not-a-valid-date"]},
    )
    assert response.status_code == 422
    assert "Invalid date in weeks parameter" in response.json()["detail"]


def test_missing_telemetry_file_returns_503(tmp_path: pathlib.Path):
    """Verify that a missing telemetry dataset raises FileNotFoundError and returns HTTP 503."""
    empty_dir = tmp_path / "nonexistent_dir"
    empty_telemetry_repo = TelemetryRepository(data_dir=empty_dir)
    empty_gateway_repo = GatewayRepository(data_dir=empty_dir)
    empty_service = PredictionService(
        telemetry_repo=empty_telemetry_repo,
        gateway_repo=empty_gateway_repo,
        ranker=ThreeSigmaRanker(),
    )

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: empty_service
    app.dependency_overrides[get_telemetry_repository] = lambda: empty_telemetry_repo
    app.dependency_overrides[get_gateway_repository] = lambda: empty_gateway_repo

    client = TestClient(app)
    response = client.get("/predictions/2026-02-02")
    assert response.status_code == 503
    assert response.json()["error_type"] == "FileNotFoundError"
    assert "Required data file is missing" in response.json()["detail"]


def test_dashboard_endpoint(test_client: TestClient):
    """GET / and GET /dashboard should return 200 with HTML content."""
    res1 = test_client.get("/")
    assert res1.status_code == 200
    assert "VoxBridge" in res1.text
    assert "text/html" in res1.headers["content-type"]

    res2 = test_client.get("/dashboard")
    assert res2.status_code == 200
    assert "VoxBridge" in res2.text

