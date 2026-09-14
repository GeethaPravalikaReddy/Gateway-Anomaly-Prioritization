"""Three-Sigma Anomaly Detection and Ranking Implementation."""

from __future__ import annotations

import datetime as dt
import re

import numpy as np
import pandas as pd

from src.config import settings
from src.core.models import GatewayMetricStats, GatewayScoreDetail, PredictionRecord

_BARE = re.compile(r"^[0-9A-Fa-f]{12}$")
_COLON = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_gateway_id(value: str) -> str:
    """Normalize gateway ID to 12 uppercase hexadecimal characters."""
    text = str(value).strip()
    if _COLON.match(text):
        return text.replace(":", "").upper()
    if _BARE.match(text):
        return text.upper()
    return text.upper()


class ThreeSigmaRanker:
    """Ranks gateways based on 3-sigma anomaly breaches across trailing telemetry.

    Methodology:
    1. Extracts trailing baseline window (28 days strictly before target Monday).
    2. Calculates baseline mean and standard deviation per gateway for key metrics:
       (`offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`).
    3. Evaluates trailing recent window (7 days strictly before target Monday).
    4. Flags hours where any metric exceeds its gateway-specific mean by > 3 standard deviations.
    5. Aggregates total flagged hours per gateway, sorts descending, and formats reasons.
    """

    def __init__(
        self,
        metrics: list[str] | None = None,
        baseline_days: int | None = None,
        recent_days: int | None = None,
        sigma_threshold: float | None = None,
    ) -> None:
        self.metrics = metrics or settings.METRICS
        self.baseline_days = baseline_days or settings.BASELINE_DAYS
        self.recent_days = recent_days or settings.RECENT_DAYS
        self.sigma_threshold = sigma_threshold or settings.SIGMA_THRESHOLD

    def _prepare_window(
        self, frame: pd.DataFrame, monday: dt.date
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split telemetry into baseline window (28d) and recent window (7d)."""
        end = pd.Timestamp(monday, tz="UTC")
        baseline_start = end - dt.timedelta(days=self.baseline_days)
        recent_start = end - dt.timedelta(days=self.recent_days)

        window = frame[(frame["ts"] >= baseline_start) & (frame["ts"] < end)]
        if window.empty:
            return window, pd.DataFrame(), pd.DataFrame()

        recent = window[window["ts"] >= recent_start].copy()
        return window, recent, end

    def rank_week(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        top_n: int = 15,
    ) -> list[PredictionRecord]:
        """Rank gateways for a given Monday."""
        window, recent, _ = self._prepare_window(frame, monday)
        if window.empty or recent.empty:
            return []

        stats = window.groupby("gateway_id")[self.metrics].agg(["mean", "std"])

        flags = pd.Series(0, index=recent.index, dtype=int)
        worst = pd.Series("", index=recent.index, dtype=object)

        for metric in self.metrics:
            mean = recent["gateway_id"].map(stats[(metric, "mean")])
            std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
            exceeded = (recent[metric] - mean) > (self.sigma_threshold * std)
            exceeded = exceeded.fillna(False)
            flags = flags + exceeded.astype(int)
            worst = worst.where(~exceeded | (worst != ""), metric)

        recent["flagged"] = flags
        recent["worst_metric"] = worst

        grouped = recent.groupby("gateway_id").agg(
            flagged_hours=("flagged", "sum"),
            worst_metric=("worst_metric", lambda s: next((v for v in s if v), "")),
        ).reset_index()

        # Enforce deterministic secondary tie-breaking: flagged_hours DESC, normalized gateway_id ASC
        grouped["normalized_id"] = grouped["gateway_id"].apply(normalize_gateway_id)
        ranked = grouped.sort_values(
            by=["flagged_hours", "normalized_id"],
            ascending=[False, True],
        ).reset_index(drop=True)

        results: list[PredictionRecord] = []
        for rank, row in enumerate(ranked.head(top_n).itertuples(index=False), 1):
            metric = row.worst_metric or f"no metric over {int(self.sigma_threshold)} sigma"
            flagged = int(row.flagged_hours)
            reason = (
                f"{flagged} hour(s) beyond {int(self.sigma_threshold)} sigma of this gateway's own "
                f"{self.baseline_days}-day baseline in the last {self.recent_days} days; "
                f"first breach on {metric}"
            )
            # Ensure strictly within 300 character requirement
            if len(reason) > 300:
                reason = reason[:297] + "..."

            results.append(
                PredictionRecord(
                    week_start=monday.isoformat(),
                    rank=rank,
                    gateway_id=row.normalized_id,
                    score=float(flagged),
                    reason=reason,
                )
            )
        return results

    def explain_gateway(
        self,
        frame: pd.DataFrame,
        monday: dt.date,
        gateway_id: str,
    ) -> GatewayScoreDetail | None:
        """Provide detailed metric statistics and anomaly explanation for a gateway."""
        norm_id = normalize_gateway_id(gateway_id)

        # Check if gateway exists in frame (handling both bare and colon formatted IDs in source data)
        norm_series = frame["gateway_id"].astype(str).str.replace(":", "").str.upper()
        gw_frame = frame[norm_series == norm_id]
        if gw_frame.empty:
            return None

        # Full ranking for the week to locate relative rank and score
        all_ranked = self.rank_week(frame, monday, top_n=len(norm_series.unique()))
        gw_prediction = next((p for p in all_ranked if p.gateway_id == norm_id), None)

        window, recent, _ = self._prepare_window(gw_frame, monday)
        if window.empty:
            return GatewayScoreDetail(
                gateway_id=norm_id,
                week_start=monday.isoformat(),
                rank=None,
                total_flagged_hours=0,
                score=0.0,
                first_breach_metric="no telemetry in baseline window",
                reason="No telemetry recorded in the 28-day baseline window.",
                metric_breakdown=[],
                recent_total_hours_observed=0,
                baseline_total_hours_observed=0,
            )

        metric_stats_list: list[GatewayMetricStats] = []
        for metric in self.metrics:
            m_series = window[metric].dropna()
            mean_val = float(m_series.mean()) if not m_series.empty else 0.0
            std_val = float(m_series.std()) if not m_series.empty else 0.0
            thresh = mean_val + (self.sigma_threshold * std_val)

            breaches = 0
            if not recent.empty and metric in recent.columns and std_val > 0:
                breaches = int((recent[metric] > thresh).sum())

            metric_stats_list.append(
                GatewayMetricStats(
                    metric_name=metric,
                    mean=round(mean_val, 4),
                    std=round(std_val, 4),
                    threshold_3sigma=round(thresh, 4),
                    recent_breaches_count=breaches,
                )
            )

        total_flagged = int(gw_prediction.score) if gw_prediction else 0
        rank_val = gw_prediction.rank if gw_prediction else None
        reason_val = gw_prediction.reason if gw_prediction else "Not ranked in top dispatches."
        first_breach = (
            next((m.metric_name for m in metric_stats_list if m.recent_breaches_count > 0), "none")
        )

        return GatewayScoreDetail(
            gateway_id=norm_id,
            week_start=monday.isoformat(),
            rank=rank_val,
            total_flagged_hours=total_flagged,
            score=float(total_flagged),
            first_breach_metric=first_breach,
            reason=reason_val,
            metric_breakdown=metric_stats_list,
            recent_total_hours_observed=len(recent),
            baseline_total_hours_observed=len(window),
        )
