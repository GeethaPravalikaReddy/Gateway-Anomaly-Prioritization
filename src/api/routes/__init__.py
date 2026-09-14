"""API Route Handlers."""

from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.gateways import router as gateways_router
from src.api.routes.health import router as health_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.routes.predictions import router as predictions_router

__all__ = [
    "dashboard_router",
    "gateways_router",
    "health_router",
    "pipeline_router",
    "predictions_router",
]
