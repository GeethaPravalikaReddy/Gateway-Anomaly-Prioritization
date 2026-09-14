"""FastAPI dependency injection providers."""

from __future__ import annotations

from functools import lru_cache

from src.config import settings
from src.core.ranker_3sigma import ThreeSigmaRanker
from src.data.repository import GatewayRepository, TelemetryRepository
from src.services.prediction_service import PredictionService


@lru_cache()
def get_telemetry_repository() -> TelemetryRepository:
    """Provide singleton instance of TelemetryRepository."""
    return TelemetryRepository(settings.DATA_DIR)


@lru_cache()
def get_gateway_repository() -> GatewayRepository:
    """Provide singleton instance of GatewayRepository."""
    return GatewayRepository(settings.DATA_DIR)


@lru_cache()
def get_prediction_service() -> PredictionService:
    """Provide singleton instance of PredictionService with injected 3-sigma ranker."""
    return PredictionService(
        telemetry_repo=get_telemetry_repository(),
        gateway_repo=get_gateway_repository(),
        ranker=ThreeSigmaRanker(),
    )
