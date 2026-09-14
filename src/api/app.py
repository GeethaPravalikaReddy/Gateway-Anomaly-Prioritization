"""FastAPI application factory and middleware configuration."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import (
    dashboard_router,
    gateways_router,
    health_router,
    pipeline_router,
    predictions_router,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI web service instance."""
    app = FastAPI(
        title="Gateway Anomaly Prioritization - Gateway Anomaly & Prioritization API",
        description=(
            "Production-ready REST API for LPDG Radio Network field technician dispatch prioritization, "
            "anomaly detection, and telemetry analytics."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Enable CORS for browser integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(dashboard_router)
    app.include_router(health_router)
    app.include_router(predictions_router)
    app.include_router(pipeline_router)
    app.include_router(gateways_router)

    # Custom Exception Handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc), "error_type": "ValueError"},
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": f"Required data file is missing: {exc}",
                "error_type": "FileNotFoundError",
            },
        )

    return app


app = create_app()
