"""Reusable short-term traffic-demand prediction utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "timestamp_utc",
    "intersection_id",
    "intersection_name",
    "approach",
    "lane_count",
    "vehicle_count_15min",
    "avg_speed_kmh",
    "queue_length_m",
    "is_rush_hour",
    "weather",
}
GROUP_COLUMNS = ["intersection_id", "approach"]
FEATURE_COLUMNS = [
    "vehicle_count_15min",
    "queue_length_m",
    "avg_speed_kmh",
    "is_rush_hour",
    "lane_count",
    "vehicle_count_lag_15",
    "vehicle_count_lag_30",
    "vehicle_count_lag_45",
    "hour",
    "minute",
    "day_of_week",
    "intersection_id",
    "approach",
    "weather",
]
NUMERIC_FEATURES = [
    "vehicle_count_15min",
    "queue_length_m",
    "avg_speed_kmh",
    "is_rush_hour",
    "lane_count",
    "vehicle_count_lag_15",
    "vehicle_count_lag_30",
    "vehicle_count_lag_45",
    "hour",
    "minute",
    "day_of_week",
]
CATEGORICAL_FEATURES = ["intersection_id", "approach", "weather"]


def load_and_engineer_features(path: str | Path) -> pd.DataFrame:
    """Load the sensor CSV and build leakage-safe grouped forecasting rows."""
    frame = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")

    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    if frame["timestamp_utc"].isna().any():
        raise ValueError("Dataset contains invalid timestamps.")
    frame = frame.sort_values(GROUP_COLUMNS + ["timestamp_utc"]).reset_index(drop=True)

    grouped = frame.groupby(GROUP_COLUMNS, sort=False)
    frame["target_next_vehicle_count"] = grouped["vehicle_count_15min"].shift(-1)
    frame["vehicle_count_lag_15"] = grouped["vehicle_count_15min"].shift(1)
    frame["vehicle_count_lag_30"] = grouped["vehicle_count_15min"].shift(2)
    frame["vehicle_count_lag_45"] = grouped["vehicle_count_15min"].shift(3)
    frame["hour"] = frame["timestamp_utc"].dt.hour
    frame["minute"] = frame["timestamp_utc"].dt.minute
    frame["day_of_week"] = frame["timestamp_utc"].dt.dayofweek
    return frame


def model_feature_columns() -> list[str]:
    """Return the exact feature order used for training and prediction."""
    return FEATURE_COLUMNS.copy()
