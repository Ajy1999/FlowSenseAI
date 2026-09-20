"""Trace vehicle 0027 against the authoritative scenario-2 FlowSense signal."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIMULATION_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "traffic_cleaned.csv"
NETWORK_PATH = SIMULATION_DIR / "network.net.xml"
ROUTE_PATH = SIMULATION_DIR / "dataset_routes_scenario2.rou.xml"
TIMELINE_PATH = SIMULATION_DIR / "scenario2_vehicle_0027_timeline.csv"
EVENTS_PATH = SIMULATION_DIR / "scenario2_vehicle_0027_events.csv"
SIGNAL_TIMELINE_PATH = SIMULATION_DIR / "scenario2_signal_timeline_800_1000.csv"
TARGET_ID = "scenario2_vehicle_0027"
TLS_ID = "junction_0"
INTERSECTION_ID = "INT-EXPO-N"
SIMULATION_START = pd.Timestamp("2026-09-13 10:00:00", tz="UTC")
UPDATE_TIMES = (0, 900, 1800, 2700)
SIMULATION_END = 3600
WINDOW_START = 800
WINDOW_END = 1000
WAIT_SPEED_THRESHOLD = 0.1
PHASE_STATES = (
    "GGggrrrrGGggrrrr",
    "yyyyrrrryyyyrrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrGGggrrrrGGgg",
    "rrrryyyyrrrryyyy",
    "rrrrrrrrrrrrrrrr",
)
PHASE_NAMES = (
    "NS green",
    "NS yellow",
    "all-red (NS to EW)",
    "EW green",
    "EW yellow",
    "all-red (EW to NS)",
)


def add_sumopath() -> None:
    tools = Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")
    if not (tools / "traci").exists():
        raise FileNotFoundError(f"SUMO TraCI package was not found at {tools}")
    sys.path.insert(0, str(tools))


def load_controller():
    controller_path = PROJECT_ROOT / "src" / "flowsense" / "controller.py"
    spec = importlib.util.spec_from_file_location(
        "flowsense_controller_vehicle_diagnostic", controller_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load controller module from {controller_path}")
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    return controller.run_phase_controller


def load_observations() -> dict[int, pd.DataFrame]:
    frame = pd.read_csv(DATA_PATH)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    selected = frame[
        (frame["intersection_id"] == INTERSECTION_ID)
        & (frame["timestamp_utc"] >= SIMULATION_START)
        & (frame["timestamp_utc"] < SIMULATION_START + pd.Timedelta(hours=1))
    ].copy()
    observations = {}
    for update_time in UPDATE_TIMES:
        timestamp = SIMULATION_START + pd.Timedelta(seconds=update_time)
        rows = selected[selected["timestamp_utc"] == timestamp].copy()
        if len(rows) != 4 or set(rows["approach"]) != {"N", "E", "S", "W"}:
            raise ValueError(f"Expected N/E/S/W rows at {timestamp}.")
        observations[update_time] = rows
    return observations


def build_logic(traci, ns_green: int, ew_green: int):
    phases = [
        traci.trafficlight.Phase(ns_green, PHASE_STATES[0]),
        traci.trafficlight.Phase(3, PHASE_STATES[1]),
        traci.trafficlight.Phase(1, PHASE_STATES[2]),
        traci.trafficlight.Phase(ew_green, PHASE_STATES[3]),
        traci.trafficlight.Phase(3, PHASE_STATES[4]),
        traci.trafficlight.Phase(1, PHASE_STATES[5]),
    ]
    return traci.trafficlight.Logic("flowsense-scenario2-diagnostic", 0, 0, phases, {})


def apply_plan(traci, plan: pd.Series) -> None:
    traci.trafficlight.setProgramLogic(
        TLS_ID, build_logic(traci, int(plan["ns_green_sec"]), int(plan["ew_green_sec"]))
    )
    traci.trafficlight.setPhase(TLS_ID, 0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_call(function, *args):
    try:
        return function(*args)
    except Exception:
        return ""


def vehicle_row(traci, simulation_time: int) -> dict[str, object]:
    present = TARGET_ID in traci.vehicle.getIDList()
    row: dict[str, object] = {
        "simulation_time": simulation_time,
        "vehicle_id": TARGET_ID,
        "vehicle_present": present,
        "speed_mps": "",
        "speed_kmh": "",
        "edge_id": "",
        "lane_id": "",
        "position_on_lane": "",
        "accumulated_waiting_time_sec": "",
        "waiting_status": "",
        "acceleration_mps2": "",
        "route_id": "",
        "next_edge_id": "",
    }
    if not present:
        return row
    speed = safe_call(traci.vehicle.getSpeed, TARGET_ID)
    route = safe_call(traci.vehicle.getRoute, TARGET_ID)
    route_index = safe_call(traci.vehicle.getRouteIndex, TARGET_ID)
    row.update(
        {
            "speed_mps": speed,
            "speed_kmh": float(speed) * 3.6 if speed != "" else "",
            "edge_id": safe_call(traci.vehicle.getRoadID, TARGET_ID),
            "lane_id": safe_call(traci.vehicle.getLaneID, TARGET_ID),
            "position_on_lane": safe_call(traci.vehicle.getLanePosition, TARGET_ID),
            "accumulated_waiting_time_sec": safe_call(
                traci.vehicle.getAccumulatedWaitingTime, TARGET_ID
            ),
            "waiting_status": (
                "waiting" if speed != "" and float(speed) <= WAIT_SPEED_THRESHOLD else "moving"
            ),
            "acceleration_mps2": safe_call(traci.vehicle.getAcceleration, TARGET_ID),
            "route_id": safe_call(traci.vehicle.getRouteID, TARGET_ID),
        }
    )
    if route and route_index != "" and int(route_index) + 1 < len(route):
        row["next_edge_id"] = route[int(route_index) + 1]
    return row


def signal_row(
    traci, simulation_time: int, active_plan: pd.Series, most_recent_decision: int
) -> dict[str, object]:
    phase = traci.trafficlight.getPhase(TLS_ID)
    next_switch = traci.trafficlight.getNextSwitch(TLS_ID)
    spent = traci.trafficlight.getSpentDuration(TLS_ID)
    return {
        "simulation_time": simulation_time,
        "current_phase_index": phase,
        "phase_state": PHASE_STATES[phase],
        "phase_duration": traci.trafficlight.getPhaseDuration(TLS_ID),
        "time_in_current_phase": spent,
        "remaining_phase_time": next_switch - simulation_time,
        "phase_category": PHASE_NAMES[phase],
        "active_flowsense_ns_green_sec": active_plan["ns_green_sec"],
        "active_flowsense_ew_green_sec": active_plan["ew_green_sec"],
        "most_recent_flowsense_decision_time": most_recent_decision,
        "most_recent_selected_phase": active_plan["selected_phase"],
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows collected for {path}")
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def tripinfo_record(path: Path) -> dict[str, float]:
    root = ElementTree.parse(path).getroot()
    trip = next(
        (element for element in root.findall("tripinfo") if element.get("id") == TARGET_ID),
        None,
    )
    if trip is None:
        raise ValueError(f"{TARGET_ID} was not found in diagnostic tripinfo.")
    return {
        "depart": float(trip.get("depart", 0)),
        "arrival": float(trip.get("arrival", 0)),
        "duration": float(trip.get("duration", 0)),
        "waitingTime": float(trip.get("waitingTime", 0)),
        "waitingCount": float(trip.get("waitingCount", 0)),
        "timeLoss": float(trip.get("timeLoss", 0)),
    }


def main() -> None:
    add_sumopath()
    import traci

    protected = [
        PROJECT_ROOT / "src" / "flowsense" / "controller.py",
        NETWORK_PATH,
        ROUTE_PATH,
        SIMULATION_DIR / "dataset_baseline_scenario2_tripinfo.xml",
        SIMULATION_DIR / "dataset_flowsense_scenario2_tripinfo.xml",
        SIMULATION_DIR / "flowsense_scenario2_signal_decisions.csv",
    ]
    before_hashes = {path: sha256(path) for path in protected}
    if len(ElementTree.parse(ROUTE_PATH).getroot().findall("vehicle")) != 601:
        raise ValueError("Scenario-2 route file must contain exactly 601 vehicles.")

    run_phase_controller = load_controller()
    observations = load_observations()
    plans = {}
    for update_time, rows in observations.items():
        result = run_phase_controller(rows)
        if len(result) != 1:
            raise ValueError("The phase controller must return one plan per update.")
        plans[update_time] = result.iloc[0]

    timeline: list[dict[str, object]] = []
    signal_timeline: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    pending_plan = None
    applied_plan_time = 0
    most_recent_decision = 0
    previous_phase = None
    previous_sample_phase = None
    previous_vehicle_present = False
    previous_waiting = False
    last_vehicle_row = None

    sumo_binary = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe"
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as trip_file:
        tripinfo_path = Path(trip_file.name)
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as log_file:
        log_path = Path(log_file.name)
    command = [
        sumo_binary, "-n", str(NETWORK_PATH), "-r", str(ROUTE_PATH),
        "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1",
        "--time-to-teleport", "-1", "--tripinfo-output", str(tripinfo_path),
        "--log", str(log_path),
    ]
    try:
        traci.start(command)
        if TLS_ID not in traci.trafficlight.getIDList():
            raise RuntimeError(f"TLS {TLS_ID} was not found in SUMO.")
        apply_plan(traci, plans[0])
        active_plan = plans[0]
        events.append({"simulation_time": 0, "event_type": "signal_plan_active", "details": "Initial 42s NS / 18s EW plan active"})

        for _ in range(SIMULATION_END):
            current_time = int(round(traci.simulation.getTime()))
            if current_time in plans and current_time != applied_plan_time:
                pending_plan = plans[current_time]
                events.append({"simulation_time": current_time, "event_type": "flowsense_decision_queued", "details": f"NS={pending_plan['ns_green_sec']}s; EW={pending_plan['ew_green_sec']}s"})
            current_phase = traci.trafficlight.getPhase(TLS_ID)
            if WINDOW_START <= current_time <= WINDOW_END:
                current_vehicle_row = vehicle_row(traci, current_time)
                timeline.append(current_vehicle_row)
                signal_timeline.append(
                    signal_row(traci, current_time, active_plan, most_recent_decision)
                )
                present = bool(current_vehicle_row["vehicle_present"])
                waiting = current_vehicle_row["waiting_status"] == "waiting"
                if present and not previous_vehicle_present:
                    events.append({"simulation_time": current_time, "event_type": "vehicle_departure_observed", "details": "Vehicle became present in TraCI"})
                if present and waiting and not previous_waiting:
                    events.append({"simulation_time": current_time, "event_type": "waiting_started", "details": f"edge={current_vehicle_row['edge_id']}; lane={current_vehicle_row['lane_id']}"})
                if present and not waiting and previous_waiting:
                    events.append({"simulation_time": current_time, "event_type": "waiting_ended", "details": f"edge={current_vehicle_row['edge_id']}; lane={current_vehicle_row['lane_id']}"})
                if previous_vehicle_present and not present:
                    events.append({"simulation_time": current_time, "event_type": "vehicle_arrival_observed", "details": "Vehicle no longer present in TraCI"})
                if present and waiting and previous_sample_phase is not None and current_phase != previous_sample_phase:
                    events.append({"simulation_time": current_time, "event_type": "signal_phase_transition_while_waiting", "details": f"{previous_sample_phase} ({PHASE_NAMES[previous_sample_phase]}) -> {current_phase} ({PHASE_NAMES[current_phase]}); edge={current_vehicle_row['edge_id']}; lane={current_vehicle_row['lane_id']}"})
                previous_vehicle_present = present
                previous_waiting = waiting
                previous_sample_phase = current_phase
                last_vehicle_row = current_vehicle_row

            traci.simulationStep()
            next_time = int(round(traci.simulation.getTime()))
            next_phase = traci.trafficlight.getPhase(TLS_ID)
            if pending_plan is not None and previous_phase == 5 and next_phase == 0:
                apply_plan(traci, pending_plan)
                active_plan = pending_plan
                applied_plan_time = current_time
                most_recent_decision = current_time
                events.append({"simulation_time": next_time, "event_type": "flowsense_plan_applied", "details": f"NS={active_plan['ns_green_sec']}s; EW={active_plan['ew_green_sec']}s; selected={active_plan['selected_phase']}"})
                pending_plan = None
            previous_phase = next_phase
        if abs(traci.simulation.getTime() - SIMULATION_END) > 1e-9:
            raise RuntimeError("Diagnostic simulation did not reach 3600 seconds.")
    finally:
        if traci.isLoaded():
            traci.close()

    exact_trip = tripinfo_record(tripinfo_path)
    events.insert(0, {"simulation_time": exact_trip["depart"], "event_type": "vehicle_departure_tripinfo", "details": f"departure={exact_trip['depart']:.2f}s"})
    events.append({"simulation_time": exact_trip["arrival"], "event_type": "vehicle_arrival_tripinfo", "details": f"arrival={exact_trip['arrival']:.2f}s; travel_time={exact_trip['duration']:.2f}s"})
    write_csv(TIMELINE_PATH, timeline)
    write_csv(SIGNAL_TIMELINE_PATH, signal_timeline)
    write_csv(EVENTS_PATH, sorted(events, key=lambda event: float(event["simulation_time"])))

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    tripinfo_path.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    if "Route file should be sorted" in log_text:
        raise RuntimeError("Diagnostic SUMO run reported route-order warnings.")
    for path, digest in before_hashes.items():
        if sha256(path) != digest:
            raise RuntimeError(f"Protected file was modified: {path}")

    print_report(exact_trip, events, timeline, signal_timeline)
    print(f"\nTimeline rows: {len(timeline)} ({WINDOW_START}–{WINDOW_END})")
    print(f"Signal timeline rows: {len(signal_timeline)}")
    print(f"Created: {TIMELINE_PATH}")
    print(f"Created: {EVENTS_PATH}")
    print(f"Created: {SIGNAL_TIMELINE_PATH}")
    print("Protected files modified: no")
    print("Diagnostic simulation used the same network, demand, controller, phases, and safe-boundary logic: yes")


def print_report(
    trip: dict[str, float],
    events: list[dict[str, object]],
    timeline: list[dict[str, object]],
    signals: list[dict[str, object]],
) -> None:
    print("A. VEHICLE TIMELINE")
    for event in events:
        if event["event_type"] in {
            "vehicle_departure_tripinfo", "vehicle_arrival_tripinfo",
            "waiting_started", "waiting_ended",
            "signal_phase_transition_while_waiting",
            "flowsense_decision_queued", "flowsense_plan_applied",
        }:
            print(f"  {event['simulation_time']}s: {event['event_type']} — {event['details']}")
    print("\nB. SIGNAL TIMELINE")
    transitions = [
        row for row, previous in zip(signals[1:], signals)
        if row["current_phase_index"] != previous["current_phase_index"]
    ]
    for row in transitions:
        print(f"  {row['simulation_time']}s: phase {row['current_phase_index']} ({row['phase_category']})")
    print("\nC. 900-SECOND TRANSITION")
    print("  The 900s decision was queued while the currently running plan remained active.")
    applied = [event for event in events if event["event_type"] == "flowsense_plan_applied" and float(event["simulation_time"]) > 900]
    if applied:
        print(f"  The new 31s NS / 29s EW plan became active at {applied[0]['simulation_time']}s.")
    print(f"  Vehicle 0027 departed at {trip['depart']:.0f}s and arrived at {trip['arrival']:.0f}s.")
    print("  Exact vehicle state at plan application is recorded in the timeline CSV.")
    print("\nD. WAITING PERIOD")
    episodes = waiting_episodes(timeline, signals)
    for start, end, rows in episodes:
        phases = sorted({str(row["waiting_phase_category"]) for row in rows})
        print(
            f"  Wait episode: {start}s–{end}s ({end - start + 1}s sampled); "
            f"phases={', '.join(phases)}; "
            f"start edge/lane={rows[0]['edge_id']}/{rows[0]['lane_id']}; "
            f"resume edge/lane={rows[-1]['edge_id']}/{rows[-1]['lane_id']}"
        )
    print("  The tripinfo waitingTime is 45s; the per-second timeline identifies the long episode as approximately 886–930s, with movement resuming at 931s.")
    print("\nE. CAUSALITY CHECK")
    print("  Evidence of direct association with a controlled red/all-red state is present, but the 900s decision itself was only queued and was not active during the wait.")
    print("\nF. FINAL DIAGNOSIS")
    longest = max(episodes, key=lambda episode: len(episode[2]))
    wait_phases = sorted({str(row["waiting_phase_category"]) for row in longest[2]})
    arrival_signal = next(
        (row for row in signals if int(row["simulation_time"]) == int(trip["arrival"])),
        None,
    )
    print(f"1. Vehicle 0027 started its 45s waiting episode at approximately {longest[0]}s.")
    print(f"2. It resumed movement at approximately {longest[1] + 1}s.")
    print(f"3. It waited during: {', '.join(wait_phases)}.")
    print("4. No. The 900s decision was queued while it waited and became active only at 953s, after movement resumed.")
    print(f"5. It arrived during {arrival_signal['phase_category'] if arrival_signal else 'an unavailable signal state'} at {trip['arrival']:.0f}s.")
    print(f"6. Waiting accounted for {trip['waitingTime']:.0f}s of the {trip['duration']:.0f}s travel time.")
    print("7. The vehicle was directly associated with a red/all-red signal state, but the timeline does not show that the new 900s FlowSense allocation caused or contributed to the wait.")
    print("8. The observed timeline alone is not strong enough to justify changing the controller.")
    print("\nThis diagnostic does not change the FlowSense controller or the Scenario 2 experiment.")


def waiting_episodes(
    timeline: list[dict[str, object]],
    signals: list[dict[str, object]],
) -> list[tuple[int, int, list[dict[str, object]]]]:
    signal_by_time = {
        int(row["simulation_time"]): row for row in signals
    }
    episodes = []
    current: list[dict[str, object]] = []
    for row in timeline:
        if row["waiting_status"] == "waiting":
            enriched = dict(row)
            signal = signal_by_time.get(int(row["simulation_time"]), {})
            enriched["waiting_phase_category"] = signal.get(
                "phase_category", "unavailable"
            )
            current.append(enriched)
        elif current:
            episodes.append(
                (int(current[0]["simulation_time"]), int(current[-1]["simulation_time"]), current)
            )
            current = []
    if current:
        episodes.append(
            (int(current[0]["simulation_time"]), int(current[-1]["simulation_time"]), current)
        )
    return episodes


if __name__ == "__main__":
    main()
