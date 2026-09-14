"""Health check and service status route."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from src.api.dependencies import get_prediction_service
from src.api.schemas import HealthResponse
from src.services.prediction_service import PredictionService

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    service: PredictionService = Depends(get_prediction_service),
) -> HealthResponse:
    """Check service health, telemetry data availability, and algorithm configuration."""
    status_dict = service.get_health_status()
    return HealthResponse(**status_dict)
