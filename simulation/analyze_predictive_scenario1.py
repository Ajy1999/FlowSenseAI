"""Compare fixed-time, reactive, and predictive Scenario 1 tripinfo."""

from pathlib import Path
from statistics import median
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
SIMULATION_DIR = ROOT / "simulation"
PREDICTIVE_DIR = ROOT / "outputs" / "validation_predictive"
PATHS = {
    "fixed_time": SIMULATION_DIR / "dataset_baseline_tripinfo.xml",
    "reactive_flowsense": SIMULATION_DIR / "dataset_flowsense_tripinfo.xml",
    "predictive_flowsense": PREDICTIVE_DIR / "predictive_scenario1_tripinfo.xml",
}


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def metrics(path: Path) -> dict[str, float]:
    root = ElementTree.parse(path).getroot()
    trips = [
        {
            "travel": float(node.get("duration", 0)),
            "waiting": float(node.get("waitingTime", 0)),
            "loss": float(node.get("timeLoss", 0)),
            "stops": float(node.get("waitingCount", 0)),
        }
        for node in root.findall("tripinfo")
    ]
    if not trips:
        raise ValueError(f"No completed trips in {path}")
    travel = [trip["travel"] for trip in trips]
    waiting = [trip["waiting"] for trip in trips]
    return {
        "completed_vehicles": float(len(trips)),
        "average_travel_time_sec": sum(travel) / len(travel),
        "median_travel_time_sec": median(travel),
        "p95_travel_time_sec": percentile(travel, 95),
        "average_waiting_time_sec": sum(waiting) / len(waiting),
        "median_waiting_time_sec": median(waiting),
        "p95_waiting_time_sec": percentile(waiting, 95),
        "average_time_loss_sec": sum(trip["loss"] for trip in trips) / len(trips),
        "average_stops": sum(trip["stops"] for trip in trips) / len(trips),
        "maximum_waiting_time_sec": max(waiting),
        "maximum_travel_time_sec": max(travel),
    }


def main() -> None:
    results = {name: metrics(path) for name, path in PATHS.items()}
    print("Scenario 1: INT-EXPO-E, 2026-09-17 09:00–10:00 UTC")
    print("Metric | Fixed-time | Reactive FlowSense | Predictive FlowSense")
    print("--- | ---: | ---: | ---:")
    keys = list(next(iter(results.values())))
    for key in keys:
        print(
            f"{key} | {results['fixed_time'][key]:.3f} | "
            f"{results['reactive_flowsense'][key]:.3f} | "
            f"{results['predictive_flowsense'][key]:.3f}"
        )
    print("\nPredictive decision diagnostics are in:")
    print(PREDICTIVE_DIR / "predictive_decision_log.csv")


if __name__ == "__main__":
    main()
