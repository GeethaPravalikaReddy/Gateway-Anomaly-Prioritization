"""Pytest configuration, shared fixtures, and synthetic datasets."""

from __future__ import annotations

import datetime as dt
import numpy as np
import pandas as pd
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


@pytest.fixture
def synthetic_telemetry_df() -> pd.DataFrame:
    """Generate deterministic synthetic telemetry for 20 gateways across 35 days.

    Includes:
    - 1 highly anomalous gateway ('0A0000000001') with distinct 3-sigma spikes in the recent 7-day window.
    - 1 completely flatline gateway ('000000000000') with 0 variance.
    - 18 normal gateways with Gaussian noise.
    """
    np.random.seed(42)
    start_ts = pd.Timestamp("2026-01-05 00:00:00", tz="UTC")
    total_hours = 35 * 24  # 35 days of hourly records
    timestamps = [start_ts + pd.Timedelta(hours=i) for i in range(total_hours)]

    gateways = [f"0A{i:010X}" for i in range(1, 20)]
    gateways.append("000000000000")  # zero variance gateway

    rows = []
    for ts in timestamps:
        for gw in gateways:
            if gw == "000000000000":
                # Flatline: 0 offline, 0 disconnection, 0 reboots always
                offline = 0.0
                discon = 0
                reboot = 0
            elif gw == "0A0000000001":
                # Baseline: 10 with low variance.
                # In last 7 days (2026-01-26 to 2026-02-02), 40 distinct hours spike to 50,000 sec offline
                is_recent = ts >= pd.Timestamp("2026-01-26 00:00:00", tz="UTC")
                is_spike = is_recent and (ts.hour in [2, 3, 4, 14, 15, 16])
                offline = 50000.0 if is_spike else 10.0 + np.random.normal(0, 0.5)
                discon = 20 if is_spike else 0
                reboot = 5 if is_spike else 0
            else:
                # Normal gateways: low noise
                offline = max(0.0, float(np.random.normal(5, 1)))
                discon = int(np.random.poisson(0.2))
                reboot = 1 if np.random.rand() < 0.005 else 0

            rows.append(
                {
                    "gateway_id": gw,
                    "ts": ts,
                    "offline_duration_sec": offline,
                    "disconnection_cnt": discon,
                    "reboot_cnt": reboot,
                }
            )

    return pd.DataFrame(rows)


@pytest.fixture
def mock_telemetry_repo(synthetic_telemetry_df: pd.DataFrame) -> TelemetryRepository:
    """TelemetryRepository backed by synthetic DataFrame."""
    repo = TelemetryRepository()
    repo._frame = synthetic_telemetry_df
    return repo


@pytest.fixture
def mock_gateway_repo() -> GatewayRepository:
    """GatewayRepository backed by synthetic master metadata."""
    repo = GatewayRepository()
    repo._master = pd.DataFrame(
        [
            {
                "gateway_id": "0A0000000001",
                "tenant": "Utility A",
                "site_type": "rooftop",
                "region": "Berlin",
                "hw_model": "GW-200",
                "antenna_type": "omni",
                "fw_version": "v1.2.0",
                "installed_on": "2024-01-10",
                "decommissioned_on": "",
                "n_meters_installed": 350,
            },
            {
                "gateway_id": "000000000000",
                "tenant": "Utility B",
                "site_type": "basement",
                "region": "Munich",
                "hw_model": "GW-100",
                "antenna_type": "directional",
                "fw_version": "v1.0.0",
                "installed_on": "2023-05-15",
                "decommissioned_on": "",
                "n_meters_installed": 120,
            },
        ]
    )
    return repo


@pytest.fixture
def mock_prediction_service(
    mock_telemetry_repo: TelemetryRepository, mock_gateway_repo: GatewayRepository
) -> PredictionService:
    """PredictionService configured with synthetic data repositories."""
    return PredictionService(
        telemetry_repo=mock_telemetry_repo,
        gateway_repo=mock_gateway_repo,
        ranker=ThreeSigmaRanker(),
    )


@pytest.fixture
def test_client(
    mock_prediction_service: PredictionService,
    mock_telemetry_repo: TelemetryRepository,
    mock_gateway_repo: GatewayRepository,
) -> TestClient:
    """FastAPI TestClient with overridden dependencies."""
    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: mock_prediction_service
    app.dependency_overrides[get_telemetry_repository] = lambda: mock_telemetry_repo
    app.dependency_overrides[get_gateway_repository] = lambda: mock_gateway_repo
    return TestClient(app)
