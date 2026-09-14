"""Prediction Service coordinating data repositories and swappable rankers."""

from __future__ import annotations

import datetime as dt
import pathlib
import threading
import pandas as pd

from src.config import settings
from src.core.interfaces import BaseRanker
from src.core.models import GatewayScoreDetail, PredictionRecord
from src.core.ranker_3sigma import ThreeSigmaRanker
from src.data.repository import GatewayRepository, TelemetryRepository


class PredictionService:
    """Orchestrates telemetry data retrieval, anomaly ranking, and predictions generation.

    The ranking algorithm is decoupled via the BaseRanker protocol and injected into this
    service, allowing alternative algorithms (e.g. ML models, custom rules) to be swapped
    without modifying the API or service layer.
    """

    def __init__(
        self,
        telemetry_repo: TelemetryRepository | None = None,
        gateway_repo: GatewayRepository | None = None,
        ranker: BaseRanker | None = None,
    ) -> None:
        self.telemetry_repo = telemetry_repo or TelemetryRepository()
        self.gateway_repo = gateway_repo or GatewayRepository()
        self.ranker = ranker or ThreeSigmaRanker()
        self._lock = threading.Lock()

    def get_top_gateways(
        self,
        monday: dt.date,
        limit: int = 15,
    ) -> list[PredictionRecord]:
        """Retrieve the top prioritized gateways requiring dispatch for a specific Monday."""
        frame = self.telemetry_repo.get_telemetry()
        return self.ranker.rank_week(frame, monday, top_n=limit)

    def explain_gateway(
        self,
        monday: dt.date,
        gateway_id: str,
    ) -> GatewayScoreDetail | None:
        """Provide detailed metric statistics, thresholds, and anomaly reasons for a gateway."""
        frame = self.telemetry_repo.get_telemetry()
        return self.ranker.explain_gateway(frame, monday, gateway_id)

    def generate_full_predictions(
        self,
        output_file: pathlib.Path | str | None = None,
        weeks: list[dt.date] | None = None,
        limit_per_week: int = 15,
        reload_data: bool = True,
    ) -> pd.DataFrame:
        """Generate predictions for all scored weeks and atomically write out to CSV.

        Args:
            output_file: Path to destination CSV file.
            weeks: List of Monday dates to score.
            limit_per_week: Number of prioritized dispatches per week (default 15).
            reload_data: If True (default), forces a re-read of storage partitions,
                         ensuring newly added telemetry files are incorporated without
                         restarting the application.
        """
        with self._lock:
            target_weeks = weeks or settings.SCORED_WEEKS
            out_path = pathlib.Path(output_file or settings.OUTPUT_FILE)

            # Re-read current storage state if requested (live evaluation requirement)
            if reload_data:
                frame = self.telemetry_repo.get_telemetry(force_reload=True)
                self.gateway_repo.get_master(force_reload=True)
            else:
                frame = self.telemetry_repo.get_telemetry()

            all_records: list[PredictionRecord] = []
            for monday in target_weeks:
                week_predictions = self.ranker.rank_week(frame, monday, top_n=limit_per_week)
                if len(week_predictions) < limit_per_week:
                    raise ValueError(
                        f"Only {len(week_predictions)} gateways available for week {monday}, "
                        f"expected {limit_per_week}"
                    )
                all_records.extend(week_predictions)

            # Convert to DataFrame matching exact required columns
            df = pd.DataFrame(
                [
                    {
                        "week_start": r.week_start,
                        "rank": r.rank,
                        "gateway_id": r.gateway_id,
                        "score": r.score,
                        "reason": r.reason,
                    }
                    for r in all_records
                ]
            )

            # Atomic file write: write to temporary file first, then atomically replace.
            # Guarantees predictions.csv is never corrupted or half-written if an error occurs.
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = out_path.with_name(f".{out_path.name}.tmp")
            try:
                df.to_csv(tmp_path, index=False)
                tmp_path.replace(out_path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

            return df

    def get_health_status(self) -> dict:
        """Check availability and summary status of datasets."""
        telemetry_ok = self.telemetry_repo.is_available()
        master_df = self.gateway_repo.get_master()
        total_master_gateways = len(master_df) if not master_df.empty else 0

        telemetry_rows = 0
        if telemetry_ok:
            try:
                frame = self.telemetry_repo.get_telemetry()
                telemetry_rows = len(frame)
            except Exception:
                telemetry_ok = False

        return {
            "status": "healthy" if telemetry_ok else "degraded",
            "telemetry_available": telemetry_ok,
            "telemetry_row_count": telemetry_rows,
            "total_registered_gateways": total_master_gateways,
            "ranker_algorithm": self.ranker.__class__.__name__,
            "configured_metrics": settings.METRICS,
            "sigma_threshold": settings.SIGMA_THRESHOLD,
        }
