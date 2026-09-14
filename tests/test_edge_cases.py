"""Bug regression tests and edge cases with minimal reproducing inputs.

Verifies Round-1 and Round-2 Software Development requirements:
- "one test written because you found a bug"
- "build the smallest input that reproduces the bug you found"
- Deterministic tie-breaking behavior
- Division-by-zero resilience on flatline metrics
- Colon-separated MAC vs bare hex normalization
- Multi-encoding resilience for German localization
- Pydantic v2 NaN float serialization fix
"""

from __future__ import annotations

import datetime as dt
import numpy as np
import pandas as pd
import pytest

from src.api.schemas import GatewayMetadataResponse
from src.core.ranker_3sigma import ThreeSigmaRanker, normalize_gateway_id
from src.data.loader import load_gateway_master
from src.data.repository import GatewayRepository


# ==============================================================================
# BUG REGRESSION 1: Gateway disappearance due to colon-separated MAC formatting
# ==============================================================================
def test_bug_regression_colon_mac_gateway_disappearance():
    """Bug Regression: Minimal reproduction of gateway disappearing on colon MAC search.

    Bug Description:
        Telemetry records store bare 12-char hex IDs ('0A2778A31BE3'), while field technicians
        and external URLs supply colon-formatted strings ('0a:27:78:a3:1b:e3').
        A naive search `frame[frame['gateway_id'] == query_id]` matched 0 rows, causing
        the gateway to completely disappear from API lookups.

    Minimal Reproducing Input:
        1 gateway, 1 row of telemetry with bare hex ID.
    """
    now = pd.Timestamp("2026-02-02 00:00:00", tz="UTC")
    minimal_df = pd.DataFrame(
        [
            {
                "gateway_id": "0A2778A31BE3",
                "ts": now - pd.Timedelta(days=1),
                "offline_duration_sec": 100.0,
                "disconnection_cnt": 2,
                "reboot_cnt": 0,
            }
        ]
    )

    ranker = ThreeSigmaRanker()
    # Before the fix, searching "0a:27:78:a3:1b:e3" returned None
    detail = ranker.explain_gateway(minimal_df, dt.date(2026, 2, 2), "0a:27:78:a3:1b:e3")

    assert detail is not None, "Gateway disappeared when searched with colon format!"
    assert detail.gateway_id == "0A2778A31BE3"


# ==============================================================================
# BUG REGRESSION 2: Pydantic v2 ValidationError on NaN Float from Pandas
# ==============================================================================
def test_bug_regression_nan_float_pydantic_serialization(tmp_path):
    """Bug Regression: Minimal reproduction of Pydantic crashing on Pandas NaN floats.

    Bug Description:
        When pandas reads CSV metadata with missing values (e.g. decommissioned_on),
        it represents them as float `np.nan`.
        Passing `np.nan` into Pydantic v2's optional string field (`str | None`) raises:
        `ValidationError: Input should be a valid string [type=string_type, input_value=nan, input_type=float]`.

    Minimal Reproducing Input:
        A single CSV row with empty optional date column.
    """
    csv_file = tmp_path / "gateway_master.csv"
    csv_file.write_text(
        "gateway_id,tenant,site_type,region,hw_model,antenna_type,fw_version,installed_on,decommissioned_on,n_meters_installed\n"
        "0A1122334455,Utility_X,rooftop,Munich,GW-100,omni,v1.0,2024-01-01,,50\n"
    )

    repo = GatewayRepository(tmp_path)
    raw_record = repo.find_by_id("0A1122334455")
    assert raw_record is not None

    # Before the fix, GatewayMetadataResponse(**raw_record) raised ValidationError
    # because decommissioned_on was float('nan') instead of None.
    validated = GatewayMetadataResponse(**raw_record)
    assert validated.gateway_id == "0A1122334455"
    assert validated.decommissioned_on is None


# ==============================================================================
# BUG REGRESSION 3: Latin-1 German Character Encoding Crash (0xDF UnicodeDecodeError)
# ==============================================================================
def test_bug_regression_german_encoding_latin1_0xdf(tmp_path):
    """Bug Regression: Minimal reproduction of UnicodeDecodeError on Latin-1 German bytes.

    Bug Description:
        The challenge metadata `gateway_master.csv` contains German characters encoded as Latin-1
        (e.g., 'ß' in 'Straßenflur' encoded as byte 0xDF). Standard `pd.read_csv()` defaults to UTF-8
        and crashes with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdf`.

    Minimal Reproducing Input:
        A CSV containing the raw byte `0xDF`.
    """
    csv_bytes = b"gateway_id,tenant,site_type,region\n0A1122334455,tenant_a,rooftop,Stra\xdfenflur\n"
    test_file = tmp_path / "gateway_master.csv"
    test_file.write_bytes(csv_bytes)

    df = load_gateway_master(tmp_path)
    assert not df.empty
    assert len(df) == 1
    assert "Stra" in df.iloc[0]["region"]


# ==============================================================================
# BUG REGRESSION 4: Division by Zero & False Breach on Zero-Variance Gateways
# ==============================================================================
def test_bug_regression_zero_variance_flatline_division_by_zero():
    """Bug Regression: Minimal reproduction of standard deviation == 0 causing ZeroDivisionError.

    Bug Description:
        When a gateway has constant telemetry (e.g. 0 reboots always), std is 0.0.
        A naive formula `(val - mean) / std` divides by zero, resulting in `inf` or `NaN`,
        falsely flagging quiet gateways as massive anomalies.

    Minimal Reproducing Input:
        A gateway with constant 0 values across the baseline.
    """
    now = pd.Timestamp("2026-02-02 00:00:00", tz="UTC")
    rows = [
        {
            "gateway_id": "FLATLINE_GW",
            "ts": now - pd.Timedelta(days=28) + pd.Timedelta(hours=h),
            "offline_duration_sec": 0.0,
            "disconnection_cnt": 0,
            "reboot_cnt": 0,
        }
        for h in range(28 * 24)
    ]
    df = pd.DataFrame(rows)

    ranker = ThreeSigmaRanker()
    results = ranker.rank_week(df, dt.date(2026, 2, 2), top_n=5)
    assert len(results) == 1
    # Must flag 0 breaches, score must be 0.0
    assert results[0].score == 0.0


# ==============================================================================
# DETERMINISTIC TIE-BREAKING: Secondary Sort by Gateway ID
# ==============================================================================
def test_deterministic_tie_breaking_alphabetical():
    """Verify that gateways with identical anomaly scores break ties deterministically.

    Rule:
        1. Higher flagged_hours first (descending).
        2. In case of identical score, sort by normalized gateway_id ascending ('0A...' before '0B...' before '0C...').
    """
    now = pd.Timestamp("2026-02-02 00:00:00", tz="UTC")
    # Gateways given in reverse alphabetical order: 0C, 0B, 0A
    tied_gws = ["0C0000000001", "0B0000000001", "0A0000000001"]
    rows = []
    for gw in tied_gws:
        for h in range(28 * 24):
            ts = now - pd.Timedelta(days=28) + pd.Timedelta(hours=h)
            # All 3 have exactly 10 flagged hours in recent window
            is_spike = h >= (27 * 24) and (h % 24 < 10)
            rows.append(
                {
                    "gateway_id": gw,
                    "ts": ts,
                    "offline_duration_sec": 1000.0 if is_spike else 10.0,
                    "disconnection_cnt": 5 if is_spike else 0,
                    "reboot_cnt": 1 if is_spike else 0,
                }
            )
    df = pd.DataFrame(rows)

    ranker = ThreeSigmaRanker()
    results = ranker.rank_week(df, dt.date(2026, 2, 2), top_n=3)

    assert len(results) == 3
    # All 3 have identical score
    assert results[0].score == results[1].score == results[2].score

    # Deterministic tie-breaker must place 0A first, then 0B, then 0C
    assert results[0].gateway_id == "0A0000000001"
    assert results[0].rank == 1

    assert results[1].gateway_id == "0B0000000001"
    assert results[1].rank == 2

    assert results[2].gateway_id == "0C0000000001"
    assert results[2].rank == 3


def test_gateway_with_missing_baseline_window():
    """Edge case: Gateway appearing only in recent 7 days but missing from 28-day baseline."""
    now = pd.Timestamp("2026-02-02 00:00:00", tz="UTC")
    records = [
        {
            "gateway_id": "SPARSE_GW_01",
            "ts": now - pd.Timedelta(days=2) + pd.Timedelta(hours=h),
            "offline_duration_sec": 100,
            "disconnection_cnt": 5,
            "reboot_cnt": 2,
        }
        for h in range(48)
    ]
    df = pd.DataFrame(records)
    ranker = ThreeSigmaRanker()
    results = ranker.rank_week(df, dt.date(2026, 2, 2), top_n=5)
    assert isinstance(results, list)
