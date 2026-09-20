"""Replay 15-minute sensor bins as a store-and-forward queueing model.

Arrivals are taken from the sample CSV. Discharge uses a saturation flow of
1800 veh/h/lane, scaled by weather. Delay is uniform-delay + overflow delay
(Webster-style), which lets us compare fixed vs adaptive splits on the same
demand.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .controller import add_adaptive_plan
from .data import load_sensor_frame

SATURATION_PER_LANE_PER_HOUR = 1800.0
VEH_LENGTH_M = 7.5
BIN_HOURS = 0.25
WEATHER_SAT_FACTOR = {"clear": 1.0, "cloudy": 0.97, "light_rain": 0.88}


def _capacity(green_sec: np.ndarray, cycle_sec: np.ndarray, lanes: np.ndarray, weather: np.ndarray) -> np.ndarray:
    sat = SATURATION_PER_LANE_PER_HOUR * lanes * np.vectorize(lambda w: WEATHER_SAT_FACTOR.get(str(w), 1.0))(weather)
    return sat * (green_sec / np.maximum(cycle_sec, 1.0)) * BIN_HOURS


def _delay_hours(arrivals: np.ndarray, capacity: np.ndarray, green: np.ndarray, cycle: np.ndarray) -> np.ndarray:
    x = np.clip(arrivals / np.maximum(capacity, 1e-6), 0.0, 1.6)
    uniform = (cycle * (1.0 - green / np.maximum(cycle, 1.0)) ** 2) / (2.0 * np.maximum(1e-6, 1.0 - x * green / np.maximum(cycle, 1.0)))
    overflow = np.where(
        x > 0.9,
        900.0 * BIN_HOURS * (x - 1.0 + np.sqrt(np.maximum((x - 1.0) ** 2 + (x / np.maximum(capacity, 1.0)), 0.0))),
        0.0,
    )
    # uniform is seconds/veh; convert to vehicle-hours in the bin
    return arrivals * (uniform / 3600.0) + overflow / 3600.0


def _queue_m(arrivals: np.ndarray, capacity: np.ndarray, green: np.ndarray, cycle: np.ndarray) -> np.ndarray:
    leftover = np.maximum(0.0, arrivals - capacity)
    red_ratio = np.clip(1.0 - green / np.maximum(cycle, 1.0), 0.05, 0.95)
    cyclic = np.minimum(arrivals, capacity) * red_ratio * 0.5
    return (leftover + cyclic) * VEH_LENGTH_M


def _speed(base_speed: np.ndarray, queue_m: np.ndarray) -> np.ndarray:
    return np.clip(base_speed * (1.0 - np.minimum(queue_m, 120.0) / 220.0), 8.0, 55.0)


def score_plan(df: pd.DataFrame, green_col: str, red_col: str, prefix: str) -> pd.DataFrame:
    out = df.copy()
    green = out[green_col].to_numpy(dtype=float)
    red = out[red_col].to_numpy(dtype=float)
    cycle = green + red
    arrivals = out["vehicle_count_15min"].to_numpy(dtype=float)
    lanes = out["lane_count"].to_numpy(dtype=float)
    weather = out["weather"].to_numpy()
    cap = _capacity(green, cycle, lanes, weather)
    delay = _delay_hours(arrivals, cap, green, cycle)
    queue = _queue_m(arrivals, cap)
    served = np.minimum(arrivals, cap)
    out[f"{prefix}_capacity_veh"] = cap
    out[f"{prefix}_delay_veh_h"] = delay
    out[f"{prefix}_queue_m"] = queue
    out[f"{prefix}_throughput_veh"] = served
    out[f"{prefix}_speed_kmh"] = _speed(out["avg_speed_kmh"].to_numpy(dtype=float), queue)
    out[f"{prefix}_green_sec"] = green
    return out


def run_comparison(path: str | None = None) -> pd.DataFrame:
    df = load_sensor_frame(path)
    planned = add_adaptive_plan(df)
    scored = score_plan(planned, "signal_phase_sec_green", "signal_phase_sec_red", "baseline")
    scored = score_plan(scored, "adaptive_green_sec", "adaptive_red_sec", "adaptive")
    scored["delay_saved_veh_h"] = scored["baseline_delay_veh_h"] - scored["adaptive_delay_veh_h"]
    scored["queue_delta_m"] = scored["baseline_queue_m"] - scored["adaptive_queue_m"]
    return scored


def kpi_summary(scored: pd.DataFrame) -> dict:
    base_delay = float(scored["baseline_delay_veh_h"].sum())
    adp_delay = float(scored["adaptive_delay_veh_h"].sum())
    base_q = float(scored["baseline_queue_m"].mean())
    adp_q = float(scored["adaptive_queue_m"].mean())
    return {
        "rows": int(len(scored)),
        "intersections": int(scored["intersection_id"].nunique()),
        "days": int(scored["timestamp_utc"].dt.normalize().nunique()),
        "baseline_delay_veh_h": round(base_delay, 2),
        "adaptive_delay_veh_h": round(adp_delay, 2),
        "delay_reduction_pct": round(100.0 * (base_delay - adp_delay) / max(base_delay, 1e-9), 2),
        "baseline_mean_queue_m": round(base_q, 2),
        "adaptive_mean_queue_m": round(adp_q, 2),
        "queue_reduction_pct": round(100.0 * (base_q - adp_q) / max(base_q, 1e-9), 2),
        "baseline_throughput_veh": round(float(scored["baseline_throughput_veh"].sum()), 1),
        "adaptive_throughput_veh": round(float(scored["adaptive_throughput_veh"].sum()), 1),
        "rush_hour_delay_reduction_pct": _subset_delay_pct(scored[scored["is_rush_hour"]]),
        "rain_delay_reduction_pct": _subset_delay_pct(scored[scored["weather"] == "light_rain"]),
    }


def _subset_delay_pct(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    b = float(frame["baseline_delay_veh_h"].sum())
    a = float(frame["adaptive_delay_veh_h"].sum())
    return round(100.0 * (b - a) / max(b, 1e-9), 2)
