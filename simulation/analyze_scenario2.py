"""Analyze and compare the fixed-time and FlowSense scenario-2 runs."""

from pathlib import Path
from statistics import median
import csv
from xml.etree import ElementTree


SIMULATION_DIR = Path(__file__).resolve().parent
BASELINE_PATH = SIMULATION_DIR / "dataset_baseline_scenario2_tripinfo.xml"
FLOWSENSE_PATH = SIMULATION_DIR / "dataset_flowsense_scenario2_tripinfo.xml"
DECISIONS_PATH = SIMULATION_DIR / "flowsense_scenario2_signal_decisions.csv"
SIMULATION_DURATION_HOURS = 1.0
TRIP_ATTRIBUTES = ("waitingTime", "waitingCount", "timeLoss", "duration")
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


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def read_trips(path: Path) -> tuple[list[dict[str, float]], dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Tripinfo file does not exist: {path}")
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        raise ValueError(f"Could not parse tripinfo XML {path}: {error}") from error
    trips = []
    missing = {attribute: 0 for attribute in TRIP_ATTRIBUTES}
    for trip in root.findall("tripinfo"):
        for attribute in TRIP_ATTRIBUTES:
            if trip.get(attribute) is None:
                missing[attribute] += 1
        trips.append({
            "duration": float(trip.get("duration", 0.0)),
            "waitingTime": float(trip.get("waitingTime", 0.0)),
            "timeLoss": float(trip.get("timeLoss", 0.0)),
            "stops": float(trip.get("waitingCount", 0.0)),
        })
    if not trips:
        raise ValueError(f"No completed trips found in {path}")
    return trips, missing


def metrics(trips: list[dict[str, float]]) -> dict[str, float]:
    travel = [trip["duration"] for trip in trips]
    waiting = [trip["waitingTime"] for trip in trips]
    loss = [trip["timeLoss"] for trip in trips]
    stops = [trip["stops"] for trip in trips]
    return {
        "completed_trips": float(len(trips)),
        "average_travel_time_sec": sum(travel) / len(travel),
        "median_travel_time_sec": median(travel),
        "p95_travel_time_sec": percentile(travel, 95),
        "average_waiting_time_sec": sum(waiting) / len(waiting),
        "median_waiting_time_sec": median(waiting),
        "p95_waiting_time_sec": percentile(waiting, 95),
        "average_time_loss_sec": sum(loss) / len(loss),
        "average_stops": sum(stops) / len(stops),
        "maximum_waiting_time_sec": max(waiting),
        "maximum_travel_time_sec": max(travel),
        "throughput_completed_vehicles_per_hour": len(trips) / SIMULATION_DURATION_HOURS,
    }


def main() -> None:
    baseline_trips, baseline_missing = read_trips(BASELINE_PATH)
    flowsense_trips, flowsense_missing = read_trips(FLOWSENSE_PATH)
    baseline = metrics(baseline_trips)
    flowsense = metrics(flowsense_trips)
    print("Scenario 2: INT-EXPO-N, Expo district north approach")
    print("Window: 2026-09-13 10:00:00+00:00 to 11:00:00+00:00")
    print("Demand: N/E/S/W by interval =")
    print("  10:00: 37/29/45/41 (152)")
    print("  10:15: 43/33/28/45 (149)")
    print("  10:30: 30/41/42/37 (150)")
    print("  10:45: 32/35/41/42 (150)")
    print("\nValidation")
    print("XML parsing: successful for both tripinfo files")
    print(f"Fixed-time completed tripinfo entries: {len(baseline_trips)}")
    print(f"FlowSense completed tripinfo entries: {len(flowsense_trips)}")
    for attribute in TRIP_ATTRIBUTES:
        print(
            f"Missing {attribute}: baseline={baseline_missing[attribute]}, "
            f"FlowSense={flowsense_missing[attribute]}"
        )
    if not DECISIONS_PATH.exists():
        raise FileNotFoundError(f"Decision log does not exist: {DECISIONS_PATH}")
    with DECISIONS_PATH.open(newline="", encoding="utf-8") as source:
        decision_rows = list(csv.DictReader(source))
    print(f"FlowSense decision rows: {len(decision_rows)}")
    if len(decision_rows) != 4:
        raise ValueError(f"Expected four FlowSense decisions, found {len(decision_rows)}")
    for name, values in (("Fixed-time baseline", baseline), ("FlowSense", flowsense)):
        print(f"\n{name} metrics")
        for key, label in METRIC_LABELS.items():
            print(f"{label}: {values[key]:.3f}")
    print("\nFixed-time vs FlowSense comparison")
    print("Metric | Baseline | FlowSense | Absolute Difference | Percentage Change | Interpretation")
    print("--- | ---: | ---: | ---: | ---: | ---")
    for key, label in METRIC_LABELS.items():
        difference = flowsense[key] - baseline[key]
        if baseline[key]:
            change_text = f"{difference / baseline[key] * 100:+.3f}%"
        else:
            change_text = "N/A (baseline is zero)"
        interpretation = (
            "lower"
            if difference < 0
            else "higher"
            if difference > 0
            else "no numerical difference"
        )
        print(f"{label} | {baseline[key]:.3f} | {flowsense[key]:.3f} | {difference:+.3f} | {change_text} | FlowSense value is {interpretation}")
    print("\nFlowSense signal decisions")
    for row in decision_rows:
        print(
            f"{row['simulation_time']}s: NS={row['ns_green_sec']}s, "
            f"EW={row['ew_green_sec']}s, phase={row['selected_phase']}"
        )
    print("\nInterpretation: signs report numerical direction only. This second scenario is one validation case, not statistical proof of general improvement.")


if __name__ == "__main__":
    main()
