"""Unit tests for ThreeSigmaRanker and ranking algorithms."""

from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.core.models import PredictionRecord
from src.core.ranker_3sigma import ThreeSigmaRanker, normalize_gateway_id


def test_normalize_gateway_id():
    """Verify normalization of colon-separated and 12-char hex gateway IDs."""
    assert normalize_gateway_id("0a:27:78:a3:1b:e3") == "0A2778A31BE3"
    assert normalize_gateway_id("0A2778A31BE3") == "0A2778A31BE3"
    assert normalize_gateway_id("  0e1b6f4dba34  ") == "0E1B6F4DBA34"


def test_rank_week_synthetic(synthetic_telemetry_df: pd.DataFrame):
    """Verify that rank_week identifies the deliberately anomalous gateway as #1."""
    ranker = ThreeSigmaRanker()
    monday = dt.date(2026, 2, 2)
    top_dispatches = ranker.rank_week(synthetic_telemetry_df, monday, top_n=15)

    assert len(top_dispatches) == 15
    assert all(isinstance(r, PredictionRecord) for r in top_dispatches)

    # Gateway '0A0000000001' had massive spikes in the last 7 days
    first_rank = top_dispatches[0]
    assert first_rank.rank == 1
    assert first_rank.gateway_id == "0A0000000001"
    assert first_rank.score > 0
    assert "beyond 3 sigma" in first_rank.reason
    assert len(first_rank.reason) <= 300


def test_rank_week_empty_telemetry():
    """Verify behavior on empty dataframe."""
    ranker = ThreeSigmaRanker()
    empty_df = pd.DataFrame(columns=["gateway_id", "ts", "offline_duration_sec", "disconnection_cnt", "reboot_cnt"])
    results = ranker.rank_week(empty_df, dt.date(2026, 2, 2))
    assert results == []


def test_explain_gateway_synthetic(synthetic_telemetry_df: pd.DataFrame):
    """Verify that explain_gateway produces comprehensive metric breakdowns."""
    ranker = ThreeSigmaRanker()
    monday = dt.date(2026, 2, 2)
    detail = ranker.explain_gateway(synthetic_telemetry_df, monday, "0A0000000001")

    assert detail is not None
    assert detail.gateway_id == "0A0000000001"
    assert detail.rank == 1
    assert detail.total_flagged_hours > 0
    assert len(detail.metric_breakdown) == 3

    # Check metric breakdown details
    offline_stat = next(m for m in detail.metric_breakdown if m.metric_name == "offline_duration_sec")
    assert offline_stat.threshold_3sigma > 0
    assert offline_stat.recent_breaches_count > 0


def test_explain_unknown_gateway(synthetic_telemetry_df: pd.DataFrame):
    """Verify that explain_gateway returns None for unknown gateway."""
    ranker = ThreeSigmaRanker()
    monday = dt.date(2026, 2, 2)
    detail = ranker.explain_gateway(synthetic_telemetry_df, monday, "DEADBEEF0000")
    assert detail is None
