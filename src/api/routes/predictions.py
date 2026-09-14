"""Prediction and anomaly explanation routes."""

from __future__ import annotations

import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.dependencies import get_prediction_service
from src.api.schemas import (
    GatewayDispatchItem,
    GatewayExplanationResponse,
    MetricStatSchema,
    WeeklyPredictionResponse,
)
from src.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


def _parse_and_validate_monday(week_start_str: str) -> dt.date:
    """Parse date string and validate it represents a Monday."""
    try:
        parsed_date = dt.date.fromisoformat(week_start_str)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date format '{week_start_str}'. Expected ISO format YYYY-MM-DD.",
        )
    if parsed_date.weekday() != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date '{week_start_str}' is not a Monday. Predictions are computed for Mondays only.",
        )
    return parsed_date


@router.get("/{week_start}", response_model=WeeklyPredictionResponse)
def get_weekly_predictions(
    week_start: str = Path(
        ...,
        examples=["2026-02-02"],
        description="Monday date for the prediction week (YYYY-MM-DD)",
    ),
    limit: int = Query(
        15,
        ge=1,
        le=50,
        description="Number of top gateways to prioritize for dispatch",
    ),
    service: PredictionService = Depends(get_prediction_service),
) -> WeeklyPredictionResponse:
    """Retrieve the top prioritized gateway dispatches for a given week."""
    monday = _parse_and_validate_monday(week_start)
    records = service.get_top_gateways(monday, limit=limit)

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry data found for baseline window prior to {week_start}.",
        )

    recommendations = [
        GatewayDispatchItem(
            week_start=r.week_start,
            rank=r.rank,
            gateway_id=r.gateway_id,
            score=r.score,
            reason=r.reason,
        )
        for r in records
    ]

    return WeeklyPredictionResponse(
        week_start=week_start,
        total_dispatches=len(recommendations),
        recommendations=recommendations,
    )


@router.get("/{week_start}/gateway/{gateway_id}", response_model=GatewayExplanationResponse)
def explain_gateway_ranking(
    week_start: str = Path(..., examples=["2026-02-02"], description="Monday date (YYYY-MM-DD)"),
    gateway_id: str = Path(..., examples=["0A2778A31BE3"], description="12-char Hex Gateway ID"),
    service: PredictionService = Depends(get_prediction_service),
) -> GatewayExplanationResponse:
    """Provide a detailed explanation and metric anomaly breakdown for a specific gateway."""
    monday = _parse_and_validate_monday(week_start)
    detail = service.explain_gateway(monday, gateway_id)

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway '{gateway_id}' not found in telemetry registry.",
        )

    metric_schemas = [
        MetricStatSchema(
            metric_name=m.metric_name,
            mean=m.mean,
            std=m.std,
            threshold_3sigma=m.threshold_3sigma,
            recent_breaches_count=m.recent_breaches_count,
        )
        for m in detail.metric_breakdown
    ]

    return GatewayExplanationResponse(
        gateway_id=detail.gateway_id,
        week_start=detail.week_start,
        rank=detail.rank,
        score=detail.score,
        total_flagged_hours=detail.total_flagged_hours,
        first_breach_metric=detail.first_breach_metric,
        reason=detail.reason,
        recent_total_hours_observed=detail.recent_total_hours_observed,
        baseline_total_hours_observed=detail.baseline_total_hours_observed,
        metric_breakdown=metric_schemas,
    )
