"""Integration checks for the predictive controller before SUMO execution."""

from pathlib import Path

import importlib.util
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "outputs" / "ml_prediction" / "gradient_boosting_model.joblib"
HISTORY_PATH = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"
TIMESTAMP = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")


def load_predictive_module():
    path = ROOT / "src" / "flowsense" / "predictive_controller.py"
    spec = importlib.util.spec_from_file_location("predictive_controller_test", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load predictive controller from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    predictive = load_predictive_module()
    model = predictive.load_predictive_model(MODEL_PATH)
    history = predictive.load_prediction_history(HISTORY_PATH)
    expected_features = [
        "vehicle_count_15min", "queue_length_m", "avg_speed_kmh", "is_rush_hour",
        "lane_count", "vehicle_count_lag_15", "vehicle_count_lag_30",
        "vehicle_count_lag_45", "hour", "minute", "day_of_week",
        "intersection_id", "approach", "weather",
    ]
    fitted_features = list(model.feature_names_in_)
    assert fitted_features == expected_features
    plan, predicted = predictive.run_predictive_phase_controller(
        model,
        history,
        intersection_id="INT-EXPO-E",
        timestamp_utc=TIMESTAMP,
    )

    assert set(predicted["approach"]) == {"N", "E", "S", "W"}
    assert len(predicted) == 4
    assert pd.api.types.is_numeric_dtype(predicted["vehicle_count_15min"])
    assert predicted["vehicle_count_15min"].notna().all()
    assert (predicted["vehicle_count_15min"] >= 0).all()
    assert len(plan) == 1
    assert plan["ns_green_sec"].between(15, 45).all()
    assert plan["ew_green_sec"].between(15, 45).all()
    assert (plan["ns_green_sec"] + plan["ew_green_sec"] == 60).all()
    assert (plan["yellow_sec"] == 3).all()
    assert (plan["all_red_sec"] == 1).all()
    assert plan["ns_pressure"].between(0, 1).all()
    assert plan["ew_pressure"].between(0, 1).all()

    print("Predictive controller integration test: PASSED")
    print("Model loaded: yes")
    print("Feature contract: exact training feature order")
    print("Prediction approaches: N/E/S/W")
    print("Prediction values:", predicted.set_index("approach")["vehicle_count_15min"].to_dict())
    print(
        "Phase plan: "
        f"NS={int(plan.iloc[0]['ns_green_sec'])}s, "
        f"EW={int(plan.iloc[0]['ew_green_sec'])}s, yellow=3s, all-red=1s"
    )


if __name__ == "__main__":
    main()
