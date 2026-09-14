"""Pydantic schemas for API requests, responses, and validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GatewayDispatchItem(BaseModel):
    """Schema for a single gateway visit recommendation in weekly predictions."""

    week_start: str = Field(
        ...,
        examples=["2026-02-02"],
        description="Monday of the target week",
    )
    rank: int = Field(..., ge=1, le=15, examples=[1], description="Priority rank (1 to 15)")
    gateway_id: str = Field(..., examples=["0A2778A31BE3"], description="12-char Hex Gateway ID")
    score: float = Field(..., examples=[43.0], description="Anomaly score / flagged hour count")
    reason: str = Field(
        ...,
        max_length=300,
        examples=[
            "43 hour(s) beyond 3 sigma of this gateway's own 28-day baseline in the last 7 days; first breach on disconnection_cnt"
        ],
        description="Operations reason string",
    )


class WeeklyPredictionResponse(BaseModel):
    """Response containing ordered weekly site visit recommendations."""

    week_start: str
    total_dispatches: int
    recommendations: list[GatewayDispatchItem]


class MetricStatSchema(BaseModel):
    """Statistical baseline summary for a single metric."""

    metric_name: str
    mean: float
    std: float
    threshold_3sigma: float
    recent_breaches_count: int


class GatewayExplanationResponse(BaseModel):
    """Detailed anomaly breakdown and explanation for a specific gateway."""

    gateway_id: str
    week_start: str
    rank: int | None
    score: float
    total_flagged_hours: int
    first_breach_metric: str
    reason: str
    recent_total_hours_observed: int
    baseline_total_hours_observed: int
    metric_breakdown: list[MetricStatSchema]


class PipelineRunRequest(BaseModel):
    """Request payload to trigger batch prediction generation."""

    data_dir: str | None = Field(None, description="Custom data directory path")
    output_path: str | None = Field(None, description="Custom output CSV path")
    weeks: list[str] | None = Field(None, description="Optional list of Monday dates (YYYY-MM-DD)")


class PipelineRunResponse(BaseModel):
    """Response returned when batch predictions are generated."""

    status: str
    rows_generated: int
    scored_weeks_count: int
    output_path: str
    message: str


class HealthResponse(BaseModel):
    """Health check status response."""

    status: str
    telemetry_available: bool
    telemetry_row_count: int
    total_registered_gateways: int
    ranker_algorithm: str
    configured_metrics: list[str]
    sigma_threshold: float


class GatewayMetadataResponse(BaseModel):
    """Asset register metadata for a gateway."""

    gateway_id: str
    tenant: str | None = None
    site_type: str | None = None
    region: str | None = None
    hw_model: str | None = None
    antenna_type: str | None = None
    fw_version: str | None = None
    fw_updated_on: str | None = None
    installed_on: str | None = None
    decommissioned_on: str | None = None
    n_meters_installed: int | None = None


class ErrorResponse(BaseModel):
    """Standardized error response body."""

    detail: str
    error_type: str
