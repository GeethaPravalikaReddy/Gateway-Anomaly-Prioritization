"""Repository implementations for Telemetry and Gateway Metadata."""

from __future__ import annotations

import datetime as dt
import pathlib
import pandas as pd

from src.config import settings
from src.data.loader import load_gateway_master, load_telemetry


class TelemetryRepository:
    """Repository managing access to historical telemetry parquet partitions."""

    def __init__(self, data_dir: pathlib.Path | str | None = None) -> None:
        self.data_dir = pathlib.Path(data_dir or settings.DATA_DIR)
        self._frame: pd.DataFrame | None = None

    def get_telemetry(self, force_reload: bool = False) -> pd.DataFrame:
        """Get full pre-loaded telemetry frame, caching in memory for fast query responses."""
        if self._frame is None or force_reload:
            self._frame = load_telemetry(self.data_dir)
        return self._frame

    def get_window(
        self,
        start: dt.datetime,
        end: dt.datetime,
        gateway_id: str | None = None,
    ) -> pd.DataFrame:
        """Retrieve telemetry slice for a specific time window and optional gateway."""
        df = self.get_telemetry()
        start_ts = pd.to_datetime(start, utc=True)
        end_ts = pd.to_datetime(end, utc=True)

        mask = (df["ts"] >= start_ts) & (df["ts"] < end_ts)
        if gateway_id:
            norm_id = gateway_id.replace(":", "").upper()
            gw_mask = df["gateway_id"].astype(str).str.replace(":", "").str.upper() == norm_id
            mask = mask & gw_mask

        return df[mask]

    def invalidate(self) -> None:
        """Clear cached telemetry in memory, forcing subsequent reads to re-scan storage."""
        self._frame = None

    def reload(self) -> pd.DataFrame:
        """Explicitly reload telemetry dataset from disk."""
        return self.get_telemetry(force_reload=True)

    def is_available(self) -> bool:
        """Check if telemetry dataset directory is present and readable."""
        try:
            return (self.data_dir / "telemetry").exists() or (
                self.data_dir.exists() and any(self.data_dir.glob("*.parquet"))
            )
        except Exception:
            return False


class GatewayRepository:
    """Repository managing access to gateway asset metadata."""

    def __init__(self, data_dir: pathlib.Path | str | None = None) -> None:
        self.data_dir = pathlib.Path(data_dir or settings.DATA_DIR)
        self._master: pd.DataFrame | None = None

    def invalidate(self) -> None:
        """Clear cached master frame, forcing subsequent reads to re-scan storage."""
        self._master = None

    def reload(self) -> pd.DataFrame:
        """Explicitly reload master gateway dataset from disk."""
        return self.get_master(force_reload=True)

    def get_master(self, force_reload: bool = False) -> pd.DataFrame:
        """Get full gateway master frame."""
        if self._master is None or force_reload:
            self._master = load_gateway_master(self.data_dir)
        return self._master

    @staticmethod
    def _clean_record(row: dict) -> dict:
        """Convert float NaN/NaT values to Python None for clean JSON serialization."""
        return {k: (None if pd.isna(v) else v) for k, v in row.items()}

    def find_by_id(self, gateway_id: str) -> dict | None:
        """Find gateway metadata by ID (accepting bare or colon format)."""
        df = self.get_master()
        if df.empty:
            return None
        norm_search = gateway_id.replace(":", "").upper()
        norm_ids = df["gateway_id"].astype(str).str.replace(":", "").str.upper()
        matched = df[norm_ids == norm_search]
        if matched.empty:
            return None
        return self._clean_record(matched.iloc[0].to_dict())

    def list_gateways(
        self, tenant: str | None = None, site_type: str | None = None
    ) -> list[dict]:
        """List gateways with optional tenant / site_type filters."""
        df = self.get_master()
        if df.empty:
            return []
        subset = df.copy()
        if tenant:
            subset = subset[subset["tenant"] == tenant]
        if site_type:
            subset = subset[subset["site_type"] == site_type]
        records = subset.to_dict(orient="records")
        return [self._clean_record(r) for r in records]
