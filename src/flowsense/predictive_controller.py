"""Predictive FlowSense adapter using the frozen reactive phase controller.

Only the demand column is replaced by the trained next-15-minute forecast.
Queue, speed, pressure scoring, phase construction, and green allocation are
delegated to the existing controller implementation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APPROACH_ORDER = ("N", "E", "S", "W")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_predictive_model(model_path: str | Path) -> Any:
    """Load the persisted preprocessing-plus-regressor pipeline."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Predictive model does not exist: {path}")
    return joblib.load(path)


def load_prediction_history(history_path: str | Path) -> pd.DataFrame:
    """Load the training dataset with the exact grouped feature engineering."""
    predictor = _load_module(
        "flowsense_predictor_for_inference",
        PROJECT_ROOT / "src" / "flowsense" / "predictor.py",
    )
    return predictor.load_and_engineer_features(history_path)


def _select_history_rows(
    history: pd.DataFrame,
    intersection_id: str,
    timestamp_utc: pd.Timestamp,
) -> pd.DataFrame:
    timestamp = pd.Timestamp(timestamp_utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    rows = history[
        (history["intersection_id"] == intersection_id)
        & (history["timestamp_utc"] == timestamp)
    ].copy()
    if len(rows) != 4 or set(rows["approach"]) != set(APPROACH_ORDER):
        raise ValueError(
            f"Expected exactly N/E/S/W history rows for {intersection_id} at "
            f"{timestamp.isoformat()}, found {len(rows)}."
        )
    required = [
        "target_next_vehicle_count",
        "vehicle_count_lag_15",
        "vehicle_count_lag_30",
        "vehicle_count_lag_45",
    ]
    if rows[required].isna().any().any():
        raise ValueError(f"History features are incomplete at {timestamp.isoformat()}.")
    return rows.sort_values("approach").reset_index(drop=True)


def predict_next_demand(
    model: Any,
    history: pd.DataFrame,
    *,
    intersection_id: str,
    timestamp_utc: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return current observations and predicted N/E/S/W demand."""
    rows = _select_history_rows(history, intersection_id, timestamp_utc)
    predictor = _load_module(
        "flowsense_predictor_for_inference_columns",
        PROJECT_ROOT / "src" / "flowsense" / "predictor.py",
    )
    features = predictor.model_feature_columns()
    predictions = pd.to_numeric(model.predict(rows[features]), errors="raise")
    if len(predictions) != 4 or not pd.Series(predictions).notna().all():
        raise ValueError("Predictive model returned invalid prediction values.")
    if (predictions < 0).any():
        raise ValueError("Predictive model returned negative vehicle counts.")

    predicted = rows[
        ["timestamp_utc", "intersection_id", "approach", "queue_length_m",
         "avg_speed_kmh", "lane_count", "is_rush_hour", "weather"]
    ].copy()
    predicted["vehicle_count_15min"] = predictions.astype(float)
    predicted = predicted[
        ["timestamp_utc", "intersection_id", "approach", "vehicle_count_15min",
         "queue_length_m", "avg_speed_kmh", "lane_count", "is_rush_hour", "weather"]
    ]
    return rows, predicted


def run_predictive_phase_controller(
    model: Any,
    history: pd.DataFrame,
    *,
    intersection_id: str,
    timestamp_utc: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Predict demand and pass it through the unchanged phase-plan logic."""
    _, predicted = predict_next_demand(
        model,
        history,
        intersection_id=intersection_id,
        timestamp_utc=timestamp_utc,
    )
    controller = _load_module(
        "flowsense_controller_for_predictive",
        PROJECT_ROOT / "src" / "flowsense" / "controller.py",
    )
    plan = controller.run_phase_controller(predicted)
    return plan, predicted
