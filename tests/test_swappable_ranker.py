"""Tests demonstrating ranker swappability via the BaseRanker protocol.

Verifies the Round-1/Round-2 Software Development architectural requirement:
The ranking algorithm must be swappable without modifying the API layer,
controllers, or Pydantic schemas.
"""

from __future__ import annotations

import datetime as dt
import pandas as pd
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import get_prediction_service
from src.core.interfaces import BaseRanker
from src.core.models import GatewayScoreDetail, PredictionRecord
from src.services.prediction_service import PredictionService


class AlternativePriorityRanker:
    """Alternative ranking algorithm (e.g. business-critical or ML heuristic).

    Implements the BaseRanker protocol without subclassing.
    Ranks gateways by a static high-priority emergency rule.
    """

    def rank_week(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        top_n: int = 15,
    ) -> list[PredictionRecord]:
        """Return custom priority records with distinct custom reasons."""
        return [
            PredictionRecord(
                week_start=monday.isoformat(),
                rank=i,
                gateway_id=f"CUSTOM_GW_{i:02d}",
                score=100.0 - i,
                reason=f"Prioritized by AlternativePriorityRanker rule: score {100.0 - i}",
            )
            for i in range(1, top_n + 1)
        ]

    def explain_gateway(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> GatewayScoreDetail | None:
        """Return custom explanation detail."""
        return GatewayScoreDetail(
            gateway_id=gateway_id,
            week_start=monday.isoformat(),
            rank=1,
            total_flagged_hours=99,
            score=99.0,
            first_breach_metric="alternative_heuristic",
            reason="Explained by AlternativePriorityRanker.",
            metric_breakdown=[],
        )


def test_base_ranker_protocol_compliance():
    """Verify AlternativePriorityRanker satisfies the BaseRanker protocol at runtime."""
    ranker = AlternativePriorityRanker()
    assert isinstance(ranker, BaseRanker)


def test_swappable_ranker_serves_via_api_without_code_changes(mock_telemetry_repo, mock_gateway_repo):
    """Verify that injecting AlternativePriorityRanker into PredictionService works seamlessly across API endpoints."""
    # 1. Instantiate PredictionService with the alternative ranker
    custom_service = PredictionService(
        telemetry_repo=mock_telemetry_repo,
        gateway_repo=mock_gateway_repo,
        ranker=AlternativePriorityRanker(),
    )

    # 2. Inject into FastAPI application via dependency override
    app = create_app()
    app.dependency_overrides[get_prediction_service] = lambda: custom_service

    client = TestClient(app)

    # 3. Call GET /predictions/2026-02-02
    res = client.get("/predictions/2026-02-02?limit=5")
    assert res.status_code == 200
    data = res.json()

    assert data["total_dispatches"] == 5
    first_item = data["recommendations"][0]
    assert first_item["gateway_id"] == "CUSTOM_GW_01"
    assert first_item["score"] == 99.0
    assert "AlternativePriorityRanker" in first_item["reason"]

    # 4. Call GET /predictions/2026-02-02/gateway/CUSTOM_GW_01
    res_explain = client.get("/predictions/2026-02-02/gateway/CUSTOM_GW_01")
    assert res_explain.status_code == 200
    explain_data = res_explain.json()
    assert explain_data["gateway_id"] == "CUSTOM_GW_01"
    assert explain_data["reason"] == "Explained by AlternativePriorityRanker."
