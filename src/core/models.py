"""Domain models and data structures for ranking and anomalies."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PredictionRecord:
    """A single prediction record matching the official submission schema."""

    week_start: str  # YYYY-MM-DD
    rank: int  # 1 to 15
    gateway_id: str  # Normalized gateway identifier
    score: float  # Anomaly score / flagged hours
    reason: str  # Clear explanation <= 300 chars


@dataclass
class GatewayMetricStats:
    """Baseline summary statistics for a single metric."""

    metric_name: str
    mean: float
    std: float
    threshold_3sigma: float
    recent_breaches_count: int


@dataclass
class GatewayScoreDetail:
    """In-depth breakdown of a gateway's ranking and anomalies for a given week."""

    gateway_id: str
    week_start: str
    rank: int | None
    total_flagged_hours: int
    score: float
    first_breach_metric: str
    reason: str
    metric_breakdown: list[GatewayMetricStats] = field(default_factory=list)
    recent_total_hours_observed: int = 0
    baseline_total_hours_observed: int = 0


@dataclass
class GatewayRanking:
    """Ranking summary result for a gateway."""

    gateway_id: str
    flagged_hours: int
    score: float
    worst_metric: str
