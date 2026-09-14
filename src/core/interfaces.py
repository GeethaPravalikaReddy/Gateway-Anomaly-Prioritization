"""Abstract ranking interfaces and protocols."""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable

import pandas as pd

from src.core.models import GatewayScoreDetail, PredictionRecord


@runtime_checkable
class BaseRanker(Protocol):
    """Protocol defining the interface for gateway anomaly ranking algorithms."""

    def rank_week(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        top_n: int = 15,
    ) -> list[PredictionRecord]:
        """Rank gateways for a specific Monday.

        Args:
            frame: Telemetry DataFrame containing historical timestamps and metrics.
            monday: The target Monday date for which recommendations are generated.
            top_n: The maximum number of top gateways to return (default 15).

        Returns:
            List of PredictionRecord instances ordered by priority rank (1..top_n).
        """
        ...

    def explain_gateway(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> GatewayScoreDetail | None:
        """Provide detailed metric anomalies and statistics for a specific gateway and week.

        Args:
            frame: Telemetry DataFrame.
            monday: Target Monday date.
            gateway_id: Target gateway ID.

        Returns:
            GatewayScoreDetail if gateway has telemetry, else None.
        """
        ...
