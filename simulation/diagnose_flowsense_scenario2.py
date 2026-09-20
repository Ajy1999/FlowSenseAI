"""Diagnose extreme trip times in the isolated FlowSense scenario 2."""

from __future__ import annotations

import csv
from pathlib import Path
from xml.etree import ElementTree


SIMULATION_DIR = Path(__file__).resolve().parent
BASELINE_PATH = SIMULATION_DIR / "dataset_baseline_scenario2_tripinfo.xml"
FLOWSENSE_PATH = SIMULATION_DIR / "dataset_flowsense_scenario2_tripinfo.xml"
DECISIONS_PATH = SIMULATION_DIR / "flowsense_scenario2_signal_decisions.csv"
TRANSITION_TIMES = (0, 900, 1800, 2700)
TRANSITION_WINDOW_SECONDS = 68


def read_tripinfo(path: Path) -> dict[str, dict[str, object]]:
    """Read tripinfo records, preserving raw lane fields when available."""
    if not path.exists():
        raise FileNotFoundError(f"Tripinfo file does not exist: {path}")
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        raise ValueError(f"Could not parse {path}: {error}") from error

    trips = {}
    for element in root.findall("tripinfo"):
        trip = {
            "id": element.get("id", ""),
            "depart": float(element.get("depart", 0.0)),
            "arrival": float(element.get("arrival", 0.0)),
            "duration": float(element.get("duration", 0.0)),
            "waitingTime": float(element.get("waitingTime", 0.0)),
            "waitingCount": float(element.get("waitingCount", 0.0)),
            "timeLoss": float(element.get("timeLoss", 0.0)),
            "departLane": element.get("departLane", ""),
            "arrivalLane": element.get("arrivalLane", ""),
        }
        trips[str(trip["id"])] = trip
    if not trips:
        raise ValueError(f"No tripinfo entries found in {path}")
    return trips


def read_decisions() -> list[dict[str, str]]:
    if not DECISIONS_PATH.exists():
        raise FileNotFoundError(f"Decision log does not exist: {DECISIONS_PATH}")
    with DECISIONS_PATH.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 4:
        raise ValueError(f"Expected four decision rows, found {len(rows)}")
    return rows


def print_trip(label: str, trip: dict[str, object]) -> None:
    print(f"\n{label}")
    print(f"  vehicle ID: {trip['id']}")
    print(f"  departure time: {trip['depart']:.2f} s")
    print(f"  arrival time: {trip['arrival']:.2f} s")
    print(f"  travel time: {trip['duration']:.2f} s")
    print(f"  waiting time: {trip['waitingTime']:.2f} s")
    print(f"  waiting count: {trip['waitingCount']:.0f}")
    print(f"  time loss: {trip['timeLoss']:.2f} s")
    print(f"  number of stops: {trip['waitingCount']:.0f}")
    if trip["departLane"] or trip["arrivalLane"]:
        print(f"  depart lane (raw XML): {trip['departLane']}")
        print(f"  arrival lane (raw XML): {trip['arrivalLane']}")
        print("  route/approach: not inferred from lane fields")


def print_top(label: str, trips: list[dict[str, object]], field: str) -> None:
    print(f"\nTop 5 {label}")
    for rank, trip in enumerate(
        sorted(trips, key=lambda item: float(item[field]), reverse=True)[:5],
        start=1,
    ):
        print(
            f"  {rank}. {trip['id']}: {float(trip[field]):.2f} "
            f"(depart={float(trip['depart']):.2f}s, "
            f"arrival={float(trip['arrival']):.2f}s, "
            f"waiting={float(trip['waitingTime']):.2f}s, "
            f"stops={float(trip['waitingCount']):.0f})"
        )


def nearest_transition(trip: dict[str, object]) -> tuple[int, float]:
    """Return the closest requested plan time to the trip's active interval."""
    midpoint = (float(trip["depart"]) + float(trip["arrival"])) / 2
    nearest = min(TRANSITION_TIMES, key=lambda time: abs(midpoint - time))
    return nearest, abs(midpoint - nearest)


def print_decision_diagnostics(decisions: list[dict[str, str]]) -> None:
    print("\nFlowSense signal decisions")
    for row in decisions:
        print(
            f"  {row['simulation_time']}s: NS green={row['ns_green_sec']}s, "
            f"EW green={row['ew_green_sec']}s, phase={row['selected_phase']}, "
            f"NS pressure={row['ns_pressure']}, EW pressure={row['ew_pressure']}, "
            f"reason={row['decision_reason']}"
        )


def main() -> None:
    baseline = read_tripinfo(BASELINE_PATH)
    flowsense = read_tripinfo(FLOWSENSE_PATH)
    decisions = read_decisions()

    flow_trips = list(flowsense.values())
    baseline_trips = list(baseline.values())
    worst_flow = max(flow_trips, key=lambda trip: float(trip["duration"]))
    print("FlowSense Scenario 2 Diagnostic")
    print("================================")
    print(f"FlowSense tripinfo entries: {len(flow_trips)}")
    print(f"Baseline tripinfo entries: {len(baseline_trips)}")
    print_trip("Highest-travel-time FlowSense trip", worst_flow)

    equivalent = baseline.get(str(worst_flow["id"]))
    if equivalent is None:
        print("\nEquivalent baseline trip: not present")
    else:
        print_trip("Equivalent fixed-time baseline trip", equivalent)

    print_top("FlowSense travel times", flow_trips, "duration")
    print_top("baseline travel times", baseline_trips, "duration")
    print_top("FlowSense waiting times", flow_trips, "waitingTime")
    print_top("baseline waiting times", baseline_trips, "waitingTime")
    print_decision_diagnostics(decisions)

    nearest_time, distance = nearest_transition(worst_flow)
    print("\nTiming association check")
    print(f"  Worst FlowSense trip active interval: {worst_flow['depart']:.2f}s–{worst_flow['arrival']:.2f}s")
    print(f"  Nearest requested plan time: {nearest_time}s (midpoint distance {distance:.2f}s)")
    if distance <= TRANSITION_WINDOW_SECONDS:
        print(
            "  Result: temporal coincidence with a requested plan time is present; "
            "this is a possible association, not evidence of causation."
        )
    else:
        print("  Result: no close temporal coincidence with a requested plan time.")

    print("\nFactual diagnosis")
    print(
        f"1. The maximum FlowSense travel time was {float(worst_flow['duration']):.0f}s "
        f"for vehicle {worst_flow['id']}."
    )
    print(
        f"2. That vehicle waited {float(worst_flow['waitingTime']):.0f}s and had "
        f"{float(worst_flow['waitingCount']):.0f} waiting-count stops."
    )
    print("3. The raw tripinfo does not establish a route approach beyond its lane fields.")
    print(
        "4. The timing check reports temporal coincidence only; it does not establish "
        "that a signal plan caused the high travel time."
    )
    print(
        "5. The distributions show lower FlowSense average and 95th-percentile travel "
        "and waiting times alongside a higher maximum travel time. This is consistent "
        "with a possible small-tail trade-off in this scenario, but it is descriptive "
        "evidence from one run, not a causal or general conclusion."
    )


if __name__ == "__main__":
    main()
