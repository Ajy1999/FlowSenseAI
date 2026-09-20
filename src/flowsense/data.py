from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"


@lru_cache(maxsize=1)
def load_sensor_frame(path: str | None = None) -> pd.DataFrame:
    csv_path = Path(path) if path else DATASET_PATH
    df = pd.read_csv(csv_path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["is_rush_hour"] = df["is_rush_hour"].astype(bool)
    df["hour"] = df["timestamp_utc"].dt.hour
    df["weekday"] = df["timestamp_utc"].dt.day_name()
    df["cycle_sec"] = df["signal_phase_sec_green"] + df["signal_phase_sec_red"]
    return df.sort_values(["timestamp_utc", "intersection_id", "approach"]).reset_index(drop=True)


def intersection_meta(df: pd.DataFrame | None = None) -> pd.DataFrame:
    frame = df if df is not None else load_sensor_frame()
    return (
        frame.groupby(["intersection_id", "intersection_name"], as_index=False)
        .agg(lat=("lat", "first"), lon=("lon", "first"), lanes=("lane_count", "mean"))
        .sort_values("intersection_id")
    )
