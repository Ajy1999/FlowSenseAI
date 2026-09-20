"""Analyze completed trips from the dataset-driven fixed-time SUMO baseline."""

from pathlib import Path
from statistics import median
from xml.etree import ElementTree


SIMULATION_DIR = Path(__file__).resolve().parent
TRIPINFO_PATH = SIMULATION_DIR / "dataset_baseline_tripinfo.xml"
METRICS_PATH = SIMULATION_DIR / "dataset_baseline_metrics.csv"
SIMULATION_DURATION_HOURS = 1.0


def percentile(values: list[float], percentile_rank: float) -> float:
    """Return a linearly interpolated percentile from a non-empty list."""
    if not values:
        raise ValueError("Cannot calculate a percentile from no completed trips.")
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_rank / 100.0
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def read_tripinfo() -> list[dict[str, float]]:
    """Read completed-trip attributes from the SUMO tripinfo XML file."""
    if not TRIPINFO_PATH.exists():
        raise FileNotFoundError(f"Tripinfo file does not exist: {TRIPINFO_PATH}")

    root = ElementTree.parse(TRIPINFO_PATH).getroot()
    trips = []
    for trip in root.findall("tripinfo"):
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
    return trips


def calculate_metrics(trips: list[dict[str, float]]) -> dict[str, float]:
    """Calculate baseline trip metrics from completed SUMO tripinfo records."""
    travel_times = [trip["duration"] for trip in trips]
    waiting_times = [trip["waitingTime"] for trip in trips]
    time_losses = [trip["timeLoss"] for trip in trips]
    stops = [trip["stops"] for trip in trips]

    return {
        "completed_trips": len(trips),
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
        "throughput_completed_vehicles_per_hour": len(trips) / SIMULATION_DURATION_HOURS,
    }


def save_metrics(metrics: dict[str, float]) -> None:
    """Save metrics in the requested two-column CSV format."""
    lines = ["metric,value"]
    lines.extend(f"{name},{value:.6f}" for name, value in metrics.items())
    METRICS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Read tripinfo, calculate metrics, save them, and print a summary."""
    metrics = calculate_metrics(read_tripinfo())
    save_metrics(metrics)

    print("FlowSense Dataset Baseline Results")
    print("===================================")
    print(f"Completed trips: {int(metrics['completed_trips'])}")
    print(f"Average travel time: {metrics['average_travel_time_sec']:.3f} s")
    print(f"Median travel time: {metrics['median_travel_time_sec']:.3f} s")
    print(f"95th percentile travel time: {metrics['p95_travel_time_sec']:.3f} s")
    print(f"Average waiting time: {metrics['average_waiting_time_sec']:.3f} s")
    print(f"Median waiting time: {metrics['median_waiting_time_sec']:.3f} s")
    print(f"95th percentile waiting time: {metrics['p95_waiting_time_sec']:.3f} s")
    print(f"Average time loss: {metrics['average_time_loss_sec']:.3f} s")
    print(f"Average stops: {metrics['average_stops']:.3f}")
    print(f"Maximum waiting time: {metrics['maximum_waiting_time_sec']:.3f} s")
    print(f"Maximum travel time: {metrics['maximum_travel_time_sec']:.3f} s")
    print(
        "Throughput in completed vehicles/hour: "
        f"{metrics['throughput_completed_vehicles_per_hour']:.3f}"
    )
    print(f"Saved metrics to: {METRICS_PATH}")


if __name__ == "__main__":
    main()
