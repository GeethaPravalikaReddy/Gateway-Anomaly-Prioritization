"""Unit tests for repository data access layer."""

from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.data.repository import GatewayRepository, TelemetryRepository


def test_telemetry_repo_window_filtering(mock_telemetry_repo: TelemetryRepository):
    """Verify get_window accurately filters by datetime range and gateway ID."""
    start = dt.datetime(2026, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 1, 15, 0, 0, tzinfo=dt.timezone.utc)

    window = mock_telemetry_repo.get_window(start, end)
    assert not window.empty
    assert (window["ts"] >= start).all()
    assert (window["ts"] < end).all()

    # Filter specific gateway
    gw_window = mock_telemetry_repo.get_window(start, end, gateway_id="0A0000000001")
    assert not gw_window.empty
    assert (gw_window["gateway_id"] == "0A0000000001").all()


def test_gateway_repo_find_and_filter(mock_gateway_repo: GatewayRepository):
    """Verify master asset registry searching and filtering."""
    # Find existing
    gw = mock_gateway_repo.find_by_id("0A0000000001")
    assert gw is not None
    assert gw["tenant"] == "Utility A"
    assert gw["site_type"] == "rooftop"

    # Find non-existent
    gw_none = mock_gateway_repo.find_by_id("NONEXISTENT01")
    assert gw_none is None

    # Filter by site_type
    rooftops = mock_gateway_repo.list_gateways(site_type="rooftop")
    assert len(rooftops) == 1
    assert rooftops[0]["gateway_id"] == "0A0000000001"


def test_gateway_repo_nan_conversion(tmp_path):
    """Verify that DataFrame NaN/null values are converted to None, preventing Pydantic serialization errors."""
    csv_path = tmp_path / "gateway_master.csv"
    csv_path.write_text(
        "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,fw_updated_on,installed_on,decommissioned_on,n_meters_installed\n"
        "0A1122334455,tenant_a,rooftop,Berlin,GW-2100,Omni,3.3.1,,2023-01-01,,150\n"
    )
    repo = GatewayRepository(tmp_path)
    record = repo.find_by_id("0A1122334455")
    assert record is not None
    assert record["decommissioned_on"] is None
    assert record["fw_updated_on"] is None
    assert record["n_meters_installed"] == 150

    all_records = repo.list_gateways()
    assert len(all_records) == 1
    assert all_records[0]["decommissioned_on"] is None

