"""Analyze the completed FlowSense SUMO experiment and compare it with baseline."""

from pathlib import Path
from statistics import median
from xml.etree import ElementTree


SIMULATION_DIR = Path(__file__).resolve().parent
TRIPINFO_PATH = SIMULATION_DIR / "dataset_flowsense_tripinfo.xml"
SIMULATION_DURATION_HOURS = 1.0

BASELINE_METRICS = {
    "completed_trips": 908.0,
    "average_travel_time_sec": 55.947137,
    "median_travel_time_sec": 52.000,
    "p95_travel_time_sec": 86.000,
    "average_waiting_time_sec": 12.151982,
    "median_waiting_time_sec": 3.000,
    "p95_waiting_time_sec": 41.000,
    "average_time_loss_sec": 18.388436,
    "average_stops": 0.528634,
    "maximum_waiting_time_sec": 46.000,
    "maximum_travel_time_sec": 100.000,
    "throughput_completed_vehicles_per_hour": 908.000,
}

METRIC_LABELS = {
    "completed_trips": "Completed trips",
    "average_travel_time_sec": "Average travel time (s)",
    "median_travel_time_sec": "Median travel time (s)",
    "p95_travel_time_sec": "95th percentile travel time (s)",
    "average_waiting_time_sec": "Average waiting time (s)",
    "median_waiting_time_sec": "Median waiting time (s)",
    "p95_waiting_time_sec": "95th percentile waiting time (s)",
    "average_time_loss_sec": "Average time loss (s)",
    "average_stops": "Average stops",
    "maximum_waiting_time_sec": "Maximum waiting time (s)",
    "maximum_travel_time_sec": "Maximum travel time (s)",
    "throughput_completed_vehicles_per_hour": "Throughput (completed vehicles/hour)",
}

TRIP_ATTRIBUTES = ("waitingTime", "waitingCount", "timeLoss", "duration")


def percentile(values: list[float], percentile_rank: float) -> float:
    """Return a linearly interpolated percentile, matching baseline analysis."""
    if not values:
        raise ValueError("Cannot calculate a percentile from no completed trips.")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_rank / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def read_tripinfo() -> tuple[list[dict[str, float]], dict[str, int]]:
    """Parse FlowSense tripinfo using the baseline script's numeric definitions."""
    if not TRIPINFO_PATH.exists():
        raise FileNotFoundError(f"Tripinfo file does not exist: {TRIPINFO_PATH}")

    try:
        root = ElementTree.parse(TRIPINFO_PATH).getroot()
    except ElementTree.ParseError as error:
        raise ValueError(f"Could not parse tripinfo XML: {error}") from error

    trips = []
    missing = {attribute: 0 for attribute in TRIP_ATTRIBUTES}
    for trip in root.findall("tripinfo"):
        for attribute in TRIP_ATTRIBUTES:
            if trip.get(attribute) is None:
                missing[attribute] += 1
        trips.append(
            {
                "duration": float(trip.get("duration", 0.0)),
                "waitingTime": float(trip.get("waitingTime", 0.0)),
                "timeLoss": float(trip.get("timeLoss", 0.0)),
                "stops": float(trip.get("waitingCount", 0.0)),
            }
        )

    if not trips:
        raise ValueError(f"No completed trips were found in {TRIPINFO_PATH}")
    return trips, missing


def calculate_metrics(trips: list[dict[str, float]]) -> dict[str, float]:
    """Calculate FlowSense metrics with the baseline methodology."""
    travel_times = [trip["duration"] for trip in trips]
    waiting_times = [trip["waitingTime"] for trip in trips]
    time_losses = [trip["timeLoss"] for trip in trips]
    stops = [trip["stops"] for trip in trips]

    return {
        "completed_trips": float(len(trips)),
        "average_travel_time_sec": sum(travel_times) / len(travel_times),
        "median_travel_time_sec": median(travel_times),
        "p95_travel_time_sec": percentile(travel_times, 95),
        "average_waiting_time_sec": sum(waiting_times) / len(waiting_times),
        "median_waiting_time_sec": median(waiting_times),
        "p95_waiting_time_sec": percentile(waiting_times, 95),
        "average_time_loss_sec": sum(time_losses) / len(time_losses),
        "average_stops": sum(stops) / len(stops),
        "maximum_waiting_time_sec": max(waiting_times),
        "maximum_travel_time_sec": max(travel_times),
        "throughput_completed_vehicles_per_hour": (
            len(trips) / SIMULATION_DURATION_HOURS
        ),
    }


def percentage_change(flow: float, baseline: float) -> float:
    """Calculate percentage change while explicitly avoiding division by zero."""
    if baseline == 0:
        return 0.0 if flow == 0 else float("nan")
    return (flow - baseline) / baseline * 100.0


def difference_interpretation(difference: float) -> str:
    """Describe only the numerical direction of a comparison."""
    if difference < 0:
        return "FlowSense value is lower"
    if difference > 0:
        return "FlowSense value is higher"
    return "No numerical difference"


def print_metrics(metrics: dict[str, float]) -> None:
    """Print the FlowSense metrics before the comparison table."""
    print("FlowSense Experiment Results")
    print("============================")
    for key, label in METRIC_LABELS.items():
        value = metrics[key]
        if key == "completed_trips":
            print(f"{label}: {int(value)}")
        else:
            print(f"{label}: {value:.3f}")


def print_comparison(flow_metrics: dict[str, float]) -> None:
    """Print neutral numerical differences against the fixed-time baseline."""
    print("\nComparison with Fixed-Time Baseline")
    print("===================================")
    print(
        "Metric | Baseline | FlowSense | Absolute Difference | "
        "Percentage Change | Numerical Interpretation"
    )
    print("--- | ---: | ---: | ---: | ---: | ---")
    for key, label in METRIC_LABELS.items():
        baseline = BASELINE_METRICS[key]
        flow = flow_metrics[key]
        difference = flow - baseline
        change = percentage_change(flow, baseline)
        print(
            f"{label} | {baseline:.3f} | {flow:.3f} | "
            f"{difference:+.3f} | {change:+.3f}% | "
            f"{difference_interpretation(difference)}"
        )


def main() -> None:
    """Validate, analyze, and compare the completed FlowSense experiment."""
    try:
        trips, missing = read_tripinfo()
        metrics = calculate_metrics(trips)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"Analysis failed: {error}")
        raise SystemExit(1) from error

    print("XML parse: successful")
    print(f"FlowSense tripinfo entries analyzed: {len(trips)}")
    print("Missing optional trip attributes:")
    for attribute in TRIP_ATTRIBUTES:
        print(f"  {attribute}: {missing[attribute]}")
    print_metrics(metrics)
    print_comparison(metrics)
    print("\nDifference interpretation rules:")
    print("  Negative percentage: FlowSense numerical value is lower.")
    print("  Positive percentage: FlowSense numerical value is higher.")
    print("  Zero percentage: no numerical difference.")
    print(
        "\nCompleted trips and throughput caveat: the difference is only "
        "1 vehicle over 3600 seconds (baseline 908, FlowSense 909)."
    )
    print(
        "The +0.110% difference is a descriptive result affected by the "
        "simulation end time, not meaningful evidence of a throughput improvement."
    )
    print(
        "\nContext: lower values are generally desirable for travel time, "
        "waiting time, time loss, and maximum values."
    )
    print("Average stops are reported descriptively without a better/worse label.")
    print(
        "These results describe numerical differences in this specific one-hour "
        "experiment only; they are not evidence of general improvement."
    )
    print("\nCalculation completed successfully.")


if __name__ == "__main__":
    main()
