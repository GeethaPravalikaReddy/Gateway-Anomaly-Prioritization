"""Integration tests verifying live /pipeline/run telemetry reloading without restarting the API.

Reproduces the reviewer's exact live workflow:
1. Start the API.
2. POST /pipeline/run.
3. API remains running.
4. Add a new month partition (or updated telemetry) into data/telemetry/.
5. POST /pipeline/run AGAIN.
6. The new data on disk is actually detected without restarting the server,
   and the regenerated predictions reflect the new data.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import pandas as pd
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


def _create_minimal_telemetry_df(
    gateways: list[str],
    start_date: str,
    days: int,
    spike_gw: str | None = None,
    spike_days: int = 7,
) -> pd.DataFrame:
    """Generate minimal hourly telemetry for testing."""
    start_ts = pd.Timestamp(start_date, tz="UTC")
    total_hours = days * 24
    timestamps = [start_ts + pd.Timedelta(hours=h) for h in range(total_hours)]
    spike_start = start_ts + pd.Timedelta(days=days - spike_days)

    rows = []
    for ts in timestamps:
        for gw in gateways:
            if gw == spike_gw and ts >= spike_start and ts.hour in [2, 3, 4, 14, 15, 16]:
                # Massive anomaly breach
                offline = 50000.0
                discon = 25
                reboot = 5
            else:
                # Normal low noise
                offline = 10.0
                discon = 0
                reboot = 0

            rows.append(
                {
                    "gateway_id": gw,
                    "ts_utc": ts.isoformat(),
                    "offline_duration_sec": offline,
                    "disconnection_cnt": discon,
                    "reboot_cnt": reboot,
                }
            )
    return pd.DataFrame(rows)


def test_live_pipeline_run_detects_new_partition_for_same_week(tmp_path: pathlib.Path):
    """Workflow Test 1: Calling POST /pipeline/run, dropping a new partition on disk,

    and calling POST /pipeline/run again for the same week immediately picks up the new data.
    """
    data_dir = tmp_path / "data"
    telemetry_dir = data_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    # 1. Master asset registry with 15 gateways
    gateways = [f"0A{i:010X}" for i in range(1, 16)]
    master_rows = [
        f"{gw},Utility_A,rooftop,Berlin,GW-200,omni,v1.0,2024-01-01,,100"
        for gw in gateways
    ]
    master_csv = data_dir / "gateway_master.csv"
    master_csv.write_text(
        "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,installed_on,decommissioned_on,n_meters_installed\n"
        + "\n".join(master_rows)
        + "\n"
    )

    # 2. Initial state: Gateway 0A0000000001 has high spike anomalies
    df_m1 = _create_minimal_telemetry_df(
        gateways=gateways,
        start_date="2026-01-05 00:00:00",
        days=28,
        spike_gw="0A0000000001",
    )
    m1_dir = telemetry_dir / "month=2026-01"
    m1_dir.mkdir(parents=True, exist_ok=True)
    df_m1.to_parquet(m1_dir / "part1.parquet", index=False)

    # 3. Start API instance
    telemetry_repo = TelemetryRepository(data_dir=data_dir)
    gateway_repo = GatewayRepository(data_dir=data_dir)
    service = PredictionService(
        telemetry_repo=telemetry_repo,
        gateway_repo=gateway_repo,
        ranker=ThreeSigmaRanker(),
    )

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    app.dependency_overrides[get_telemetry_repository] = lambda: telemetry_repo
    app.dependency_overrides[get_gateway_repository] = lambda: gateway_repo

    client = TestClient(app)

    # 4. First run: target Monday is 2026-02-02
    out_file = tmp_path / "predictions_live.csv"
    res1 = client.post(
        "/pipeline/run",
        json={"output_path": str(out_file), "weeks": ["2026-02-02"]},
    )
    assert res1.status_code == 200

    df1 = pd.read_csv(out_file)
    assert df1.iloc[0]["gateway_id"] == "0A0000000001"
    assert df1.iloc[0]["score"] > 0
    # Gateway 0A0000000009 has 0 score initially
    gw9_initial = df1[df1["gateway_id"] == "0A0000000009"].iloc[0]
    assert gw9_initial["score"] == 0.0

    # 5. Reviewer action: API remains alive; drop a new telemetry partition onto disk
    # where Gateway 0A0000000009 now has massive anomaly spikes in the same week
    df_new = _create_minimal_telemetry_df(
        gateways=gateways,
        start_date="2026-01-05 00:00:00",
        days=28,
        spike_gw="0A0000000009",  # GW 9 now spikes heavily
    )
    new_dir = telemetry_dir / "month=2026-01-updated"
    new_dir.mkdir(parents=True, exist_ok=True)
    df_new.to_parquet(new_dir / "part_updated.parquet", index=False)

    # 6. Call POST /pipeline/run AGAIN with the exact same request
    res2 = client.post(
        "/pipeline/run",
        json={"output_path": str(out_file), "weeks": ["2026-02-02"]},
    )
    assert res2.status_code == 200

    df2 = pd.read_csv(out_file)
    # Gateway 0A0000000009 must now be detected with high score from disk!
    gw9_updated = df2[df2["gateway_id"] == "0A0000000009"].iloc[0]
    assert gw9_updated["score"] > 0, "New telemetry on disk was not detected by /pipeline/run!"


def test_live_pipeline_run_with_new_future_month_partition(tmp_path: pathlib.Path):
    """Workflow Test 2: Reviewer drops a new future month partition (e.g. month=2026-04/)

    onto disk and runs /pipeline/run for the new month without restarting the API.
    """
    data_dir = tmp_path / "data"
    telemetry_dir = data_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    gateways = [f"0A{i:010X}" for i in range(1, 16)]
    master_rows = [
        f"{gw},Utility_A,rooftop,Berlin,GW-200,omni,v1.0,2024-01-01,,100"
        for gw in gateways
    ]
    master_csv = data_dir / "gateway_master.csv"
    master_csv.write_text(
        "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,installed_on,decommissioned_on,n_meters_installed\n"
        + "\n".join(master_rows)
        + "\n"
    )

    # Start API with March data
    df_m3 = _create_minimal_telemetry_df(
        gateways=gateways,
        start_date="2026-03-02 00:00:00",
        days=28,
        spike_gw="0A0000000003",
    )
    m3_dir = telemetry_dir / "month=2026-03"
    m3_dir.mkdir(parents=True, exist_ok=True)
    df_m3.to_parquet(m3_dir / "part_march.parquet", index=False)

    telemetry_repo = TelemetryRepository(data_dir=data_dir)
    gateway_repo = GatewayRepository(data_dir=data_dir)
    service = PredictionService(
        telemetry_repo=telemetry_repo,
        gateway_repo=gateway_repo,
        ranker=ThreeSigmaRanker(),
    )

    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: service
    app.dependency_overrides[get_telemetry_repository] = lambda: telemetry_repo
    app.dependency_overrides[get_gateway_repository] = lambda: gateway_repo

    client = TestClient(app)

    out_file = tmp_path / "predictions_future.csv"
    # First run on March
    res1 = client.post(
        "/pipeline/run",
        json={"output_path": str(out_file), "weeks": ["2026-03-30"]},
    )
    assert res1.status_code == 200
    df1 = pd.read_csv(out_file)
    assert df1.iloc[0]["gateway_id"] == "0A0000000003"

    # Now drop April data onto disk while API is running
    df_m4 = _create_minimal_telemetry_df(
        gateways=gateways,
        start_date="2026-03-09 00:00:00",
        days=28,
        spike_gw="0A0000000007",
    )
    m4_dir = telemetry_dir / "month=2026-04"
    m4_dir.mkdir(parents=True, exist_ok=True)
    df_m4.to_parquet(m4_dir / "part_april.parquet", index=False)

    # Run for April Monday without restarting API
    res2 = client.post(
        "/pipeline/run",
        json={"output_path": str(out_file), "weeks": ["2026-04-06"]},
    )
    assert res2.status_code == 200
    df2 = pd.read_csv(out_file)
    assert len(df2) == 15
    assert df2.iloc[0]["week_start"] == "2026-04-06"
    assert df2.iloc[0]["gateway_id"] == "0A0000000007"
