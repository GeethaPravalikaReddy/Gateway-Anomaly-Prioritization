"""Data loading utilities with memory-efficient column projection."""

from __future__ import annotations

import pathlib
import pandas as pd

from src.config import settings


def load_telemetry(
    data_dir: pathlib.Path | str | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Load telemetry parquet dataset with column projection and UTC timestamp parsing.

    Args:
        data_dir: Root directory containing 'telemetry' parquet partition folder.
        columns: List of columns to project. Defaults to minimal metrics for ranking.

    Returns:
        pd.DataFrame with UTC timestamp column 'ts'.
    """
    path = pathlib.Path(data_dir or settings.DATA_DIR)
    if not path.exists():
        raise FileNotFoundError(f"Data directory not found at {path}")
    telemetry_path = path / "telemetry" if (path / "telemetry").exists() else path
    if not telemetry_path.exists():
        raise FileNotFoundError(f"Telemetry path not found at {telemetry_path}")

    cols = columns or ["gateway_id", "ts_utc", *settings.METRICS]
    # Ensure ts_utc and gateway_id are always loaded
    if "ts_utc" not in cols:
        cols.append("ts_utc")
    if "gateway_id" not in cols:
        cols.append("gateway_id")

    frame = pd.read_parquet(telemetry_path, columns=list(set(cols)))
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    if "ts_utc" in frame.columns:
        frame = frame.drop(columns=["ts_utc"])
    return frame


def load_gateway_master(data_dir: pathlib.Path | str | None = None) -> pd.DataFrame:
    """Load gateway master registry metadata with robust multi-encoding support.

    German localization in dataset includes Latin-1 encoded characters (e.g. 0xdf for 'ß').
    Attempts UTF-8 first, falling back to Latin-1/ISO-8859-1.

    Args:
        data_dir: Root directory containing 'gateway_master.csv'.

    Returns:
        pd.DataFrame with gateway asset metadata.
    """
    path = pathlib.Path(data_dir or settings.DATA_DIR)
    master_file = path / "gateway_master.csv"
    if not master_file.exists():
        return pd.DataFrame(
            columns=[
                "gateway_id",
                "tenant",
                "site_type",
                "region",
                "hw_model",
                "antenna_type",
                "fw_version",
                "installed_on",
                "decommissioned_on",
                "n_meters_installed",
            ]
        )

    try:
        return pd.read_csv(master_file, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(master_file, encoding="latin1")
