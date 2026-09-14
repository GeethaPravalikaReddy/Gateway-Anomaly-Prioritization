"""Application configuration and environment settings."""

from __future__ import annotations

import datetime as dt
import os
import pathlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Application configuration settings."""

    # Base paths
    BASE_DIR: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(__file__).resolve().parent.parent
    )
    DATA_DIR: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            os.getenv("DATA_DIR", str(pathlib.Path(__file__).resolve().parent.parent / "data"))
        )
    )
    OUTPUT_FILE: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(
            os.getenv(
                "OUTPUT_FILE",
                str(pathlib.Path(__file__).resolve().parent.parent / "predictions.csv"),
            )
        )
    )

    # Core 3-sigma algorithm parameters
    METRICS: list[str] = field(
        default_factory=lambda: ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]
    )
    VISITS_PER_WEEK: int = int(os.getenv("VISITS_PER_WEEK", "15"))
    BASELINE_DAYS: int = int(os.getenv("BASELINE_DAYS", "28"))
    RECENT_DAYS: int = int(os.getenv("RECENT_DAYS", "7"))
    SIGMA_THRESHOLD: float = float(os.getenv("SIGMA_THRESHOLD", "3.0"))

    # Scored weeks range (8 Mondays: 2026-02-02 to 2026-03-23)
    START_DATE: dt.date = dt.date(2026, 2, 2)
    NUM_SCORED_WEEKS: int = 8

    # API settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    @property
    def SCORED_WEEKS(self) -> list[dt.date]:
        """Return the list of 8 official scored Monday dates."""
        return [self.START_DATE + dt.timedelta(days=7 * i) for i in range(self.NUM_SCORED_WEEKS)]


settings = Settings()
