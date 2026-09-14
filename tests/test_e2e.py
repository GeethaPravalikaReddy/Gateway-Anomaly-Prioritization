"""End-to-End (E2E) integration tests exercising the complete real path from input files to predictions.csv.

Verifies Round-1 and Round-2 Software Development requirements:
1. Operates on self-contained small synthetic fixtures on disk (real Parquet + CSV).
2. Exercises the unmocked pipeline:
   Disk (Parquet + CSV)
        ↓
   Loader (read_parquet + read_csv with multi-encoding)
        ↓
   Repository (TelemetryRepository + GatewayRepository)
        ↓
   Ranker (ThreeSigmaRanker with deterministic tie-breaking)
        ↓
   Service (PredictionService with atomic write)
        ↓
   API (/pipeline/run route)
        ↓
   predictions.csv
        ↓
   validate_submission.py (official challenge checker)
3. Ensures 0 mocks in the middle and 0 validation errors from the grader.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import validate_submission
from src.api.app import create_app
from src.api.dependencies import (
    get_gateway_repository,
    get_prediction_service,
    get_telemetry_repository,
)
from src.config import settings
from src.core.ranker_3sigma import ThreeSigmaRanker
from src.data.repository import GatewayRepository, TelemetryRepository
from src.services.prediction_service import PredictionService


def _create_synthetic_e2e_dataset(data_dir: pathlib.Path) -> None:
    """Create minimal synthetic dataset on disk with 20 gateways across the 8 scored weeks."""
    telemetry_dir = data_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create gateway master CSV
    gateways = [f"0A{i:010X}" for i in range(1, 21)]
    master_rows = [
        f"{gw},Utility_{i%3},rooftop,Berlin,GW-200,omni,v1.0,2024-01-01,,150"
        for i, gw in enumerate(gateways)
    ]
    master_csv = data_dir / "gateway_master.csv"
    master_csv.write_text(
        "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,installed_on,decommissioned_on,n_meters_installed\n"
        + "\n".join(master_rows)
        + "\n"
    )

    # 2. Generate hourly telemetry covering 2026-01-05 through 2026-03-30 (84 days)
    # Divided into monthly partitions: 2026-01, 2026-02, 2026-03
    start_ts = pd.Timestamp("2026-01-05 00:00:00", tz="UTC")
    total_hours = 84 * 24
    timestamps = [start_ts + pd.Timedelta(hours=h) for h in range(total_hours)]

    rows = []
    for ts in timestamps:
        month_str = ts.strftime("%Y-%m")
        for i, gw in enumerate(gateways):
            # Gateway 0A0000000001 has severe intermittent breaches throughout
            if gw == "0A0000000001" and ts.hour in [2, 3, 4, 14, 15, 16]:
                offline = 45000.0
                discon = 20
                reboot = 5
            elif i % 4 == 0 and ts.hour in [3, 15]:
                offline = 1200.0
                discon = 4
                reboot = 1
            else:
                offline = 5.0
                discon = 0
                reboot = 0

            rows.append(
                {
                    "gateway_id": gw,
                    "ts_utc": ts.isoformat(),
                    "offline_duration_sec": offline,
                    "disconnection_cnt": discon,
                    "reboot_cnt": reboot,
                    "month": month_str,
                }
            )

    full_df = pd.DataFrame(rows)
    for month, group in full_df.groupby("month"):
        month_dir = telemetry_dir / f"month={month}"
        month_dir.mkdir(parents=True, exist_ok=True)
        # Drop the partition column before saving to match real partition structure
        clean_df = group.drop(columns=["month"])
        clean_df.to_parquet(month_dir / "data.parquet", index=False)


def test_e2e_synthetic_input_to_pipeline_to_predictions_validation(tmp_path: pathlib.Path):
    """Real unmocked E2E test using synthetic disk files:

    1. Writes synthetic Parquet partitions and CSV metadata to disk.
    2. Wires real TelemetryRepository, GatewayRepository, ThreeSigmaRanker, and PredictionService.
    3. Triggers /pipeline/run via the FastAPI API route.
    4. Writes predictions.csv to disk atomically.
    5. Validates output using the official validate_submission.validate() checker.
    6. Asserts 0 validation problems and exactly 120 rows generated (15 dispatches x 8 weeks).
    """
    data_dir = tmp_path / "data"
    _create_synthetic_e2e_dataset(data_dir)

    out_csv = tmp_path / "predictions_synthetic_e2e.csv"

    # Real unmocked components
    telemetry_repo = TelemetryRepository(data_dir=data_dir)
    gateway_repo = GatewayRepository(data_dir=data_dir)
    ranker = ThreeSigmaRanker()
    service = PredictionService(
        telemetry_repo=telemetry_repo,
        gateway_repo=gateway_repo,
        ranker=ranker,
    )

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    app.dependency_overrides[get_telemetry_repository] = lambda: telemetry_repo
    app.dependency_overrides[get_gateway_repository] = lambda: gateway_repo

    client = TestClient(app)

    # Trigger real /pipeline/run endpoint
    response = client.post(
        "/pipeline/run",
        json={"output_path": str(out_csv)},
    )
    assert response.status_code == 200, f"Pipeline run failed: {response.text}"
    assert out_csv.exists(), "predictions.csv was not created on disk"

    # Run official submission checker
    problems = validate_submission.validate(out_csv)
    assert problems == [], f"Official validation failed with problems: {problems}"

    # Verify contents
    df = pd.read_csv(out_csv)
    assert len(df) == 120
    assert df["week_start"].nunique() == 8
    assert all(r in list(range(1, 16)) for r in df["rank"])


def test_e2e_challenge_dataset_validation(tmp_path: pathlib.Path):
    """End-to-end test against the full challenge dataset if available locally."""
    if not settings.DATA_DIR.exists() or not (settings.DATA_DIR / "telemetry").exists():
        pytest.skip(f"Challenge dataset not found at {settings.DATA_DIR / 'telemetry'}")

    service = PredictionService()
    test_out = tmp_path / "predictions_challenge_e2e.csv"

    # Generate predictions across all 8 scored weeks
    df = service.generate_full_predictions(output_file=test_out)

    assert len(df) == 120
    assert test_out.exists()

    # Run official validator
    problems = validate_submission.validate(test_out)
    assert problems == [], f"Validation failed with problems: {problems}"
