"""Controller 1: a reactive, approach-level traffic signal policy.

The controller is intentionally limited to scoring observed traffic pressure.
It does not change signal timings, predict future traffic, or claim an
improvement over the fixed-time baseline.
"""

from pathlib import Path

import pandas as pd


PRIORITY_WEIGHTS = {
    "demand_score": 0.30,
    "queue_score": 0.40,
    "speed_congestion_score": 0.30,
}

REQUIRED_COLUMNS = {
    "timestamp_utc",
    "intersection_id",
    "approach",
    "vehicle_count_15min",
    "queue_length_m",
    "avg_speed_kmh",
}

APPROACH_ORDER = {"N": 0, "E": 1, "S": 2, "W": 3}
MIN_GREEN_SEC = 15
MAX_GREEN_SEC = 45
TOTAL_GREEN_SEC = 60
YELLOW_SEC = 3
ALL_RED_SEC = 1
PHASE_PRESSURE_TOLERANCE = 1e-9


def _validate_input_columns(frame: pd.DataFrame) -> None:
    """Raise a clear error when input is missing controller measurements."""
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Input is missing required columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("Controller input must contain at least one row.")
    if frame[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("Controller input contains null values in required columns.")


def _robust_normalize(values: pd.Series, *, invert: bool = False) -> pd.Series:
    """Normalize values to 0-1 using observed 5th and 95th percentiles.

    Clipping at observed percentiles limits outlier influence. Constant columns
    receive 0.5 because their relative pressure cannot be distinguished.
    """
    numeric_values = pd.to_numeric(values, errors="raise").astype(float)
    lower = numeric_values.quantile(0.05)
    upper = numeric_values.quantile(0.95)

    if upper <= lower:
        score = pd.Series(0.5, index=values.index, dtype=float)
    else:
        score = (
            (numeric_values.clip(lower, upper) - lower) / (upper - lower)
        ).astype(float)
    if invert:
        score = 1.0 - score
    return score.clip(0.0, 1.0)


def calculate_priority_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalized pressure components and priority score.

    Demand and queue scores increase with their measurements. Speed congestion
    increases as speed decreases. Thresholds are calculated from ``frame``.
    """
    _validate_input_columns(frame)
    scored = frame.copy()
    scored["timestamp_utc"] = pd.to_datetime(scored["timestamp_utc"], utc=True)
    scored["demand_score"] = _robust_normalize(scored["vehicle_count_15min"])
    scored["queue_score"] = _robust_normalize(scored["queue_length_m"])
    scored["speed_congestion_score"] = _robust_normalize(
        scored["avg_speed_kmh"], invert=True
    )
    scored["priority_score"] = sum(
        weight * scored[component]
        for component, weight in PRIORITY_WEIGHTS.items()
    )
    return scored


def select_priority_approaches(frame: pd.DataFrame) -> pd.DataFrame:
    """Annotate every row with its intersection/timestamp priority winner.

    Ties are resolved deterministically using N, E, S, W order. Every input
    row is retained, with the winner repeated in ``selected_approach``.
    """
    required = {"timestamp_utc", "intersection_id", "approach", "priority_score"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Input is missing score columns: {', '.join(sorted(missing))}")

    selected = frame.copy()
    selected["_approach_order"] = selected["approach"].map(APPROACH_ORDER).fillna(999)
    winners = (
        selected.sort_values(
            ["intersection_id", "timestamp_utc", "priority_score", "_approach_order"],
            ascending=[True, True, False, True],
            kind="mergesort",
        )
        .drop_duplicates(["intersection_id", "timestamp_utc"])
        [["intersection_id", "timestamp_utc", "approach"]]
        .rename(columns={"approach": "selected_approach"})
    )
    selected = selected.merge(
        winners,
        on=["intersection_id", "timestamp_utc"],
        how="left",
        validate="many_to_one",
    )
    return selected.drop(columns="_approach_order")


def allocate_green_time(frame: pd.DataFrame) -> pd.DataFrame:
    """Allocate a prototype green time from each approach priority score.

    The 15- and 45-second limits are prototype constraints for this project,
    not real Munich traffic-signal specifications. The allocation is applied
    independently to every approach and does not yet implement signal phases.
    """
    if "priority_score" not in frame.columns:
        raise ValueError("Input must contain priority_score before green-time allocation.")

    allocated = frame.copy()
    allocated["recommended_green_sec"] = (
        MIN_GREEN_SEC
        + allocated["priority_score"].clip(0.0, 1.0)
        * (MAX_GREEN_SEC - MIN_GREEN_SEC)
    ).round().astype(int)
    return allocated


def run_reactive_controller(frame: pd.DataFrame) -> pd.DataFrame:
    """Score approaches, select winners, and allocate prototype green times."""
    scored = calculate_priority_scores(frame)
    selected = select_priority_approaches(scored)
    return allocate_green_time(selected)


def _allocate_phase_green_times(
    ns_pressure: pd.Series, ew_pressure: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Allocate an exact 60-second green budget within phase limits."""
    total_pressure = ns_pressure + ew_pressure
    ns_share = ns_pressure.div(total_pressure.where(total_pressure > 0))
    ns_share = ns_share.fillna(0.5)

    ns_green = (ns_share * TOTAL_GREEN_SEC).round()
    ns_green = ns_green.clip(MIN_GREEN_SEC, MAX_GREEN_SEC).astype(int)
    ew_green = (TOTAL_GREEN_SEC - ns_green).astype(int)
    return ns_green, ew_green


def build_phase_plan(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Build one deterministic NS/EW two-phase plan per intersection/timestamp.

    ``scored_df`` must already contain the existing approach-level
    ``priority_score``. N and S are averaged into NS pressure, while E and W
    are averaged into EW pressure. The prototype uses a 60-second total green
    budget, then adds 3-second yellow and 1-second all-red transition intervals
    to each phase. These are simulation assumptions, not Munich signal specs.
    """
    required = {"timestamp_utc", "intersection_id", "approach", "priority_score"}
    missing = required.difference(scored_df.columns)
    if missing:
        raise ValueError(f"Input is missing phase-plan columns: {', '.join(sorted(missing))}")
    if scored_df.empty:
        raise ValueError("Phase-plan input must contain at least one row.")
    if scored_df[list(required)].isna().any().any():
        raise ValueError("Phase-plan input contains null values in required columns.")
    if not scored_df["priority_score"].between(0.0, 1.0).all():
        raise ValueError("priority_score must be between 0 and 1.")

    scored = scored_df.copy()
    scored["timestamp_utc"] = pd.to_datetime(scored["timestamp_utc"], utc=True)
    keys = ["intersection_id", "timestamp_utc"]
    duplicate_rows = scored.duplicated(keys + ["approach"])
    if duplicate_rows.any():
        raise ValueError("Each intersection/timestamp/approach must occur only once.")

    expected_approaches = {"N", "E", "S", "W"}
    approach_sets = scored.groupby(keys)["approach"].agg(set)
    incomplete = approach_sets[approach_sets != expected_approaches]
    if not incomplete.empty:
        raise ValueError("Each intersection/timestamp must contain exactly N, E, S, and W.")

    pressures = (
        scored.pivot(index=keys, columns="approach", values="priority_score")
        .reset_index()
        .rename_axis(None, axis=1)
    )
    pressures["ns_pressure"] = pressures[["N", "S"]].mean(axis=1)
    pressures["ew_pressure"] = pressures[["E", "W"]].mean(axis=1)
    total_pressure = pressures["ns_pressure"] + pressures["ew_pressure"]
    pressures["ns_share"] = pressures["ns_pressure"].div(
        total_pressure.where(total_pressure > 0)
    ).fillna(0.5)
    pressures["ew_share"] = pressures["ew_pressure"].div(
        total_pressure.where(total_pressure > 0)
    ).fillna(0.5)
    pressures["ns_green_sec"], pressures["ew_green_sec"] = _allocate_phase_green_times(
        pressures["ns_pressure"], pressures["ew_pressure"]
    )

    pressure_difference = pressures["ns_pressure"] - pressures["ew_pressure"]
    pressures["selected_phase"] = "BALANCED"
    pressures.loc[pressure_difference > PHASE_PRESSURE_TOLERANCE, "selected_phase"] = "NS"
    pressures.loc[pressure_difference < -PHASE_PRESSURE_TOLERANCE, "selected_phase"] = "EW"
    pressures["decision_reason"] = (
        "NS and EW traffic pressure are balanced, so green time is balanced."
    )
    pressures.loc[
        pressures["selected_phase"] == "NS", "decision_reason"
    ] = "NS phase receives more green because NS traffic pressure is higher."
    pressures.loc[
        pressures["selected_phase"] == "EW", "decision_reason"
    ] = "EW phase receives more green because EW traffic pressure is higher."

    pressures["yellow_sec"] = YELLOW_SEC
    pressures["all_red_sec"] = ALL_RED_SEC
    pressures["cycle_length_sec"] = (
        pressures["ns_green_sec"]
        + pressures["yellow_sec"]
        + pressures["all_red_sec"]
        + pressures["ew_green_sec"]
        + pressures["yellow_sec"]
        + pressures["all_red_sec"]
    )
    return pressures[
        [
            "timestamp_utc",
            "intersection_id",
            "ns_pressure",
            "ew_pressure",
            "ns_share",
            "ew_share",
            "selected_phase",
            "ns_green_sec",
            "ew_green_sec",
            "yellow_sec",
            "all_red_sec",
            "cycle_length_sec",
            "decision_reason",
        ]
    ].sort_values(keys).reset_index(drop=True)


def run_phase_controller(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate existing approach priorities and build the two-phase plan."""
    return build_phase_plan(calculate_priority_scores(frame))


def validate_phase_controller(
    data_path: str | Path, sample_rows: int = 6
) -> pd.DataFrame:
    """Run Stage 5 validation against the current cleaned traffic dataset."""
    frame = pd.read_csv(data_path)
    scored = calculate_priority_scores(frame)
    plan = build_phase_plan(scored)

    assert len(frame) == 16128
    assert frame["intersection_id"].nunique() == 6
    assert frame["approach"].nunique() == 4
    assert set(frame["approach"].unique()) == {"N", "E", "S", "W"}
    assert int(frame[list(REQUIRED_COLUMNS)].isna().sum().sum()) == 0
    assert len(plan) == frame[["intersection_id", "timestamp_utc"]].drop_duplicates().shape[0]
    assert not plan.duplicated(["intersection_id", "timestamp_utc"]).any()
    assert plan["ns_pressure"].between(0.0, 1.0).all()
    assert plan["ew_pressure"].between(0.0, 1.0).all()
    assert (plan["ns_share"] + plan["ew_share"] - 1.0).abs().lt(1e-9).all()
    assert plan["ns_green_sec"].between(MIN_GREEN_SEC, MAX_GREEN_SEC).all()
    assert plan["ew_green_sec"].between(MIN_GREEN_SEC, MAX_GREEN_SEC).all()
    assert (plan["ns_green_sec"] + plan["ew_green_sec"] == TOTAL_GREEN_SEC).all()
    assert (plan["yellow_sec"] == YELLOW_SEC).all()
    assert (plan["all_red_sec"] == ALL_RED_SEC).all()
    assert (plan["cycle_length_sec"] == 68).all()
    assert plan["selected_phase"].notna().all()
    assert plan["decision_reason"].notna().all()
    assert not (plan["ns_pressure"] + plan["ew_pressure"] == 0).any() or (
        plan.loc[
            plan["ns_pressure"] + plan["ew_pressure"] == 0,
            ["ns_share", "ew_share"],
        ]
        == 0.5
    ).all().all()

    print("Sample phase plans:")
    print(
        plan.head(sample_rows)[
            [
                "timestamp_utc",
                "intersection_id",
                "ns_pressure",
                "ew_pressure",
                "ns_green_sec",
                "ew_green_sec",
                "selected_phase",
                "decision_reason",
            ]
        ].to_string(index=False)
    )
    print("\nPhase-plan summary:")
    print(plan[["ns_pressure", "ew_pressure", "ns_green_sec", "ew_green_sec"]].describe().round(3))
    print("\nValidation passed: Stage 5 phase-plan checks.")
    return plan


def validate_controller(data_path: str | Path, sample_timestamps: int = 3) -> pd.DataFrame:
    """Load the cleaned CSV, run Controller 1, and perform current-data checks."""
    frame = pd.read_csv(data_path)
    result = run_reactive_controller(frame)

    assert len(frame) == 16128
    assert result["intersection_id"].nunique() == 6
    assert result["approach"].nunique() == 4
    assert int(frame.isna().sum().sum()) == 0

    group_sizes = result.groupby(
        ["intersection_id", "timestamp_utc"]
    )["selected_approach"].nunique()
    assert (group_sizes == 1).all()
    assert result["priority_score"].between(0.0, 1.0).all()
    assert result["recommended_green_sec"].between(
        MIN_GREEN_SEC, MAX_GREEN_SEC
    ).all()
    assert int(result.isna().sum().sum()) == 0

    print("Top-priority approaches for sample timestamps:")
    sample = result["timestamp_utc"].drop_duplicates().sort_values().head(sample_timestamps)
    display_columns = [
        "timestamp_utc", "intersection_id", "approach",
        "priority_score", "selected_approach", "recommended_green_sec",
    ]
    print(
        result[result["timestamp_utc"].isin(sample)]
        .sort_values(
            ["timestamp_utc", "intersection_id", "priority_score"],
            ascending=[True, True, False],
        )[display_columns]
        .to_string(index=False)
    )
    print("\nPriority score summary:")
    print(result["priority_score"].describe().round(3).to_string())
    print("\nValidation passed: input shape, cardinalities, nulls, selections, and score bounds.")
    return result


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    validate_controller(project_root / "data" / "processed" / "traffic_cleaned.csv")
    validate_phase_controller(project_root / "data" / "processed" / "traffic_cleaned.csv")
