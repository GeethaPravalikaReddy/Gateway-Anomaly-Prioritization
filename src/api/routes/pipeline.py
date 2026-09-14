"""Pipeline execution routes to trigger predictions generation on demand."""

from __future__ import annotations

import datetime as dt
import pathlib
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_prediction_service
from src.api.schemas import PipelineRunRequest, PipelineRunResponse
from src.config import settings
from src.services.prediction_service import PredictionService

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post("/run", response_model=PipelineRunResponse)
def run_pipeline(
    payload: PipelineRunRequest = PipelineRunRequest(),
    service: PredictionService = Depends(get_prediction_service),
) -> PipelineRunResponse:
    """Trigger full batch generation of predictions across scored weeks and export to CSV."""
    target_out = payload.output_path or str(settings.OUTPUT_FILE)

    target_weeks: list[dt.date] | None = None
    if payload.weeks:
        try:
            target_weeks = [dt.date.fromisoformat(w) for w in payload.weeks]
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid date in weeks parameter: {e}",
            )

    try:
        df = service.generate_full_predictions(
            output_file=pathlib.Path(target_out),
            weeks=target_weeks,
            reload_data=True,
        )
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline generation failed: {exc}",
        )

    weeks_count = len(target_weeks) if target_weeks else len(settings.SCORED_WEEKS)
    return PipelineRunResponse(
        status="success",
        rows_generated=len(df),
        scored_weeks_count=weeks_count,
        output_path=target_out,
        message=f"Successfully generated {len(df)} predictions across {weeks_count} weeks.",
    )
