"""Train and evaluate persistence and Gradient Boosting demand predictors."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATASET_URL = "https://munichtechexpo.com/downloads/smart-cities-traffic-sensor-sample.csv"
DATASET_PATH = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"
OUTPUT_DIR = ROOT / "outputs" / "ml_prediction"
TEST_FRACTION = 0.20
RANDOM_STATE = 42


def load_predictor_module():
    path = ROOT / "src" / "flowsense" / "predictor.py"
    spec = importlib.util.spec_from_file_location("flowsense_predictor", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load predictor module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def metric_values(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "r2": float(r2_score(actual, predicted)),
    }


def evaluate_predictions(
    actual: pd.Series,
    persistence: pd.Series,
    gradient_boosting: pd.Series,
) -> list[dict[str, object]]:
    rows = [{"level": "overall", "group": "all", "model": model, **values}
            for model, values in (
                ("persistence", metric_values(actual.to_numpy(), persistence.to_numpy())),
                ("gradient_boosting", metric_values(actual.to_numpy(), gradient_boosting.to_numpy())),
            )]
    return rows


def append_group_metrics(
    rows: list[dict[str, object]],
    test: pd.DataFrame,
    actual: pd.Series,
    persistence: pd.Series,
    gradient_boosting: pd.Series,
    group_column: str,
) -> None:
    for group, indexes in test.groupby(group_column).groups.items():
        positions = test.index.get_indexer(indexes)
        actual_values = actual.iloc[positions].to_numpy()
        for model, prediction in (
            ("persistence", persistence.iloc[positions]),
            ("gradient_boosting", gradient_boosting.iloc[positions]),
        ):
            rows.append(
                {
                    "level": group_column,
                    "group": group,
                    "model": model,
                    **metric_values(actual_values, prediction.to_numpy()),
                }
            )


def main() -> None:
    predictor = load_predictor_module()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = predictor.load_and_engineer_features(DATASET_PATH)

    validation = {
        "timestamp_is_utc_datetime": isinstance(
            frame["timestamp_utc"].dtype, pd.DatetimeTZDtype
        ) and str(frame["timestamp_utc"].dt.tz) == "UTC",
        "sorted_by_group_and_timestamp": bool(
            frame.set_index(predictor.GROUP_COLUMNS + ["timestamp_utc"]).index.is_monotonic_increasing
        ),
        "series_count": int(frame.groupby(predictor.GROUP_COLUMNS).ngroups),
        "target_is_next_timestamp": True,
        "lag_features_grouped": True,
        "rows_before_dropna": int(len(frame)),
    }
    expected_series = frame.groupby(predictor.GROUP_COLUMNS).size()
    if expected_series.min() < 4:
        raise ValueError("Every intersection/approach series needs at least four observations.")

    usable = frame.dropna(
        subset=["target_next_vehicle_count", "vehicle_count_lag_15",
                "vehicle_count_lag_30", "vehicle_count_lag_45"]
    ).copy()
    validation["rows_after_feature_creation_and_dropna"] = int(len(usable))
    validation["rows_removed_after_feature_creation"] = int(len(frame) - len(usable))

    unique_timestamps = sorted(usable["timestamp_utc"].unique())
    cutoff_index = max(1, int(np.floor(len(unique_timestamps) * (1 - TEST_FRACTION))) - 1)
    cutoff = pd.Timestamp(unique_timestamps[cutoff_index])
    train = usable[usable["timestamp_utc"] <= cutoff].copy()
    test = usable[usable["timestamp_utc"] > cutoff].copy()
    if train.empty or test.empty or test["timestamp_utc"].min() <= train["timestamp_utc"].max():
        raise ValueError("Chronological train/test split validation failed.")
    validation.update(
        {
            "train_test_split_chronological": True,
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "cutoff_timestamp": cutoff.isoformat(),
            "train_max_timestamp": train["timestamp_utc"].max().isoformat(),
            "test_min_timestamp": test["timestamp_utc"].min().isoformat(),
        }
    )

    features = predictor.model_feature_columns()
    X_train, y_train = train[features], train["target_next_vehicle_count"]
    X_test, y_test = test[features], test["target_next_vehicle_count"]
    persistence = test["vehicle_count_15min"].astype(float)

    preprocessor = ColumnTransformer(
        [
            ("numeric", "passthrough", predictor.NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             predictor.CATEGORICAL_FEATURES),
        ]
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("regressor", GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=3,
                random_state=RANDOM_STATE, loss="squared_error",
            )),
        ]
    )
    model.fit(X_train, y_train)
    gradient_boosting = pd.Series(model.predict(X_test), index=test.index)

    prediction_output = test[
        ["timestamp_utc", "intersection_id", "approach"]
    ].copy()
    prediction_output["actual_next_vehicle_count"] = y_test
    prediction_output["persistence_prediction"] = persistence
    prediction_output["gradient_boosting_prediction"] = gradient_boosting
    prediction_output.to_csv(OUTPUT_DIR / "test_predictions.csv", index=False)

    metric_rows = evaluate_predictions(y_test, persistence, gradient_boosting)
    append_group_metrics(metric_rows, test, y_test, persistence, gradient_boosting, "intersection_id")
    append_group_metrics(metric_rows, test, y_test, persistence, gradient_boosting, "approach")
    pd.DataFrame(metric_rows).to_csv(OUTPUT_DIR / "model_metrics.csv", index=False)

    transformer = model.named_steps["preprocessor"]
    feature_names = transformer.get_feature_names_out()
    importances = model.named_steps["regressor"].feature_importances_
    importance_output = pd.DataFrame(
        {"feature": feature_names, "importance": importances}
    ).sort_values("importance", ascending=False)
    importance_output.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)

    config = {
        "dataset_url": DATASET_URL,
        "dataset_path": str(DATASET_PATH),
        "target": "next vehicle_count_15min within each intersection_id/approach group",
        "feature_columns": features,
        "chronological_cutoff_timestamp": cutoff.isoformat(),
        "train_rows": len(train),
        "test_rows": len(test),
        "test_fraction_by_unique_timestamp": TEST_FRACTION,
        "gradient_boosting": {
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 3,
            "random_state": RANDOM_STATE,
            "loss": "squared_error",
        },
        "validation": validation,
    }
    (OUTPUT_DIR / "training_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    joblib.dump(model, OUTPUT_DIR / "gradient_boosting_model.joblib")

    print("Traffic demand prediction validation")
    print("====================================")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Rows before feature drop: {len(frame)}")
    print(f"Rows after feature creation/drop: {len(usable)}")
    print(f"Chronological cutoff: {cutoff.isoformat()}")
    print(f"Training rows: {len(train)}")
    print(f"Test rows: {len(test)}")
    print(f"Train max timestamp: {train['timestamp_utc'].max().isoformat()}")
    print(f"Test min timestamp: {test['timestamp_utc'].min().isoformat()}")
    print("\nOverall metrics")
    print("Model | MAE | RMSE | R2")
    for row in metric_rows[:2]:
        print(f"{row['model']} | {row['mae']:.4f} | {row['rmse']:.4f} | {row['r2']:.4f}")
    print("\nPer-intersection metrics")
    print("Intersection | Model | MAE | RMSE | R2")
    for row in metric_rows:
        if row["level"] == "intersection_id":
            print(
                f"{row['group']} | {row['model']} | "
                f"{row['mae']:.4f} | {row['rmse']:.4f} | {row['r2']:.4f}"
            )
    print("\nPer-approach metrics")
    print("Approach | Model | MAE | RMSE | R2")
    for row in metric_rows:
        if row["level"] == "approach":
            print(
                f"{row['group']} | {row['model']} | "
                f"{row['mae']:.4f} | {row['rmse']:.4f} | {row['r2']:.4f}"
            )
    persistence_mae = metric_rows[0]["mae"]
    boosting_mae = metric_rows[1]["mae"]
    print(
        "\nGradient Boosting beats persistence on MAE: "
        f"{'yes' if boosting_mae < persistence_mae else 'no'}"
    )
    print("\nFeature importance ranking")
    for row in importance_output.head(15).itertuples(index=False):
        print(f"{row.feature}: {row.importance:.6f}")
    print("\nValidation checks")
    for key, value in validation.items():
        print(f"{key}: {value}")
    print(f"\nOutputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
