"""Run the first FlowSense phase controller against the existing SUMO network.

The runner uses the unchanged 922-vehicle dataset route file. At simulation
times 0, 900, 1800, and 2700 it computes a plan through the existing
``run_phase_controller`` function. A plan requested during a cycle is queued
and installed only after phase 5 completes, so the active green/yellow/all-red
sequence is not interrupted mid-cycle.
"""

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
ROUTE_PATH = SIMULATION_DIR / "dataset_routes.rou.xml"
BASELINE_TRIPINFO_PATH = SIMULATION_DIR / "dataset_baseline_tripinfo.xml"
FLOWN_TRIPINFO_PATH = SIMULATION_DIR / "dataset_flowsense_tripinfo.xml"
DECISIONS_PATH = SIMULATION_DIR / "flowsense_signal_decisions.csv"

TLS_ID = "junction_0"
INTERSECTION_ID = "INT-EXPO-E"
SIMULATION_START = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")
UPDATE_TIMES = (0, 900, 1800, 2700)
SIMULATION_END = 3600

PHASE_STATES = (
    "GGggrrrrGGggrrrr",
    "yyyyrrrryyyyrrrr",
    "rrrrrrrrrrrrrrrr",
    "rrrrGGggrrrrGGgg",
    "rrrryyyyrrrryyyy",
    "rrrrrrrrrrrrrrrr",
)


def add_sumopath() -> None:
    """Make the TraCI package shipped with the installed SUMO available."""
    sumo_home = Path(r"C:\Program Files (x86)\Eclipse\Sumo")
    tools_path = sumo_home / "tools"
    if not (tools_path / "traci").exists():
        raise FileNotFoundError(f"SUMO TraCI package was not found at {tools_path}")
    sys.path.insert(0, str(tools_path))


def load_controller():
    """Import the existing FlowSense phase controller without duplicating it."""
    controller_path = PROJECT_ROOT / "src" / "flowsense" / "controller.py"
    spec = importlib.util.spec_from_file_location(
        "flowsense_controller_for_traci",
        controller_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load controller module from {controller_path}")
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    return controller.run_phase_controller


def load_observations() -> dict[int, pd.DataFrame]:
    """Load the four INT-EXPO-E observations used by this one-hour run."""
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
            raise ValueError(f"Expected N/E/S/W rows at {timestamp}, found {len(rows)} rows.")
        observations[update_time] = rows
    return observations


def build_phase_logic(traci, ns_green: int, ew_green: int):
    """Create the six-phase TraCI logic using the existing plan durations."""
    phases = [
        traci.trafficlight.Phase(ns_green, PHASE_STATES[0]),
        traci.trafficlight.Phase(3, PHASE_STATES[1]),
        traci.trafficlight.Phase(1, PHASE_STATES[2]),
        traci.trafficlight.Phase(ew_green, PHASE_STATES[3]),
        traci.trafficlight.Phase(3, PHASE_STATES[4]),
        traci.trafficlight.Phase(1, PHASE_STATES[5]),
    ]
    return traci.trafficlight.Logic(
        "flowsense-runtime",
        0,
        0,
        phases,
        {},
    )


def apply_plan(traci, plan: pd.Series) -> None:
    """Install one FlowSense plan and restart at the safe NS-green boundary."""
    logic = build_phase_logic(
        traci,
        int(plan["ns_green_sec"]),
        int(plan["ew_green_sec"]),
    )
    traci.trafficlight.setProgramLogic(TLS_ID, logic)
    traci.trafficlight.setPhase(TLS_ID, 0)


def route_vehicle_count() -> int:
    """Return the number of explicit vehicles in the unchanged route file."""
    root = ElementTree.parse(ROUTE_PATH).getroot()
    return len(root.findall("vehicle"))


def file_hash(path: Path) -> str:
    """Return a content hash for verifying that a protected file was unchanged."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_decisions(rows: list[dict[str, object]]) -> None:
    """Write the four requested FlowSense signal decisions."""
    columns = [
        "simulation_time",
        "dataset_timestamp",
        "ns_pressure",
        "ew_pressure",
        "ns_green_sec",
        "ew_green_sec",
        "yellow_sec",
        "all_red_sec",
        "selected_phase",
        "decision_reason",
    ]
    with DECISIONS_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Run SUMO with four dynamically applied FlowSense phase plans."""
    add_sumopath()
    import traci

    run_phase_controller = load_controller()
    observations = load_observations()
    expected_vehicles = route_vehicle_count()
    if expected_vehicles != 922:
        raise ValueError(f"Expected 922 route vehicles, found {expected_vehicles}.")
    baseline_hash = file_hash(BASELINE_TRIPINFO_PATH)

    print(f"TLS ID: {TLS_ID}")
    print(f"Route file: {ROUTE_PATH}")
    print(f"Expected vehicle count: {expected_vehicles}")

    decisions: list[dict[str, object]] = []
    plans = {}
    for update_time, rows in observations.items():
        plan = run_phase_controller(rows)
        if len(plan) != 1:
            raise ValueError("The phase controller must return one plan for each update.")
        plans[update_time] = plan.iloc[0]

    sumo_binary = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe"
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as log_file:
        log_path = Path(log_file.name)
    sumo_cmd = [
        sumo_binary,
        "-n",
        str(NETWORK_PATH),
        "-r",
        str(ROUTE_PATH),
        "--begin",
        "0",
        "--end",
        str(SIMULATION_END),
        "--step-length",
        "1",
        "--time-to-teleport",
        "-1",
        "--tripinfo-output",
        str(FLOWN_TRIPINFO_PATH),
        "--log",
        str(log_path),
    ]

    pending_plan = None
    applied_plan_time = None
    previous_phase = None
    try:
        traci.start(sumo_cmd)
        print(f"SUMO version: {traci.getVersion()[1]}")
        if TLS_ID not in traci.trafficlight.getIDList():
            raise RuntimeError(f"TLS {TLS_ID} was not found in SUMO.")

        apply_plan(traci, plans[0])
        applied_plan_time = 0
        decisions.append(
            {
                "simulation_time": 0,
                "dataset_timestamp": SIMULATION_START.isoformat(),
                "ns_pressure": plans[0]["ns_pressure"],
                "ew_pressure": plans[0]["ew_pressure"],
                "ns_green_sec": plans[0]["ns_green_sec"],
                "ew_green_sec": plans[0]["ew_green_sec"],
                "yellow_sec": plans[0]["yellow_sec"],
                "all_red_sec": plans[0]["all_red_sec"],
                "selected_phase": plans[0]["selected_phase"],
                "decision_reason": plans[0]["decision_reason"],
            }
        )
        print(
            f"FlowSense decision at 0s: NS={plans[0]['ns_green_sec']}s, "
            f"EW={plans[0]['ew_green_sec']}s, phase={plans[0]['selected_phase']}"
        )

        for simulation_time in range(SIMULATION_END):
            current_time = int(round(traci.simulation.getTime()))
            if current_time in plans and current_time != applied_plan_time:
                pending_plan = plans[current_time]
                print(
                    f"FlowSense decision at {current_time}s queued for the next "
                    f"complete cycle: NS={pending_plan['ns_green_sec']}s, "
                    f"EW={pending_plan['ew_green_sec']}s, "
                    f"phase={pending_plan['selected_phase']}"
                )
                decisions.append(
                    {
                        "simulation_time": current_time,
                        "dataset_timestamp": (
                            SIMULATION_START + pd.Timedelta(seconds=current_time)
                        ).isoformat(),
                        "ns_pressure": pending_plan["ns_pressure"],
                        "ew_pressure": pending_plan["ew_pressure"],
                        "ns_green_sec": pending_plan["ns_green_sec"],
                        "ew_green_sec": pending_plan["ew_green_sec"],
                        "yellow_sec": pending_plan["yellow_sec"],
                        "all_red_sec": pending_plan["all_red_sec"],
                        "selected_phase": pending_plan["selected_phase"],
                        "decision_reason": pending_plan["decision_reason"],
                    }
                )

            traci.simulationStep()
            phase = traci.trafficlight.getPhase(TLS_ID)
            if pending_plan is not None and previous_phase == 5 and phase == 0:
                apply_plan(traci, pending_plan)
                applied_plan_time = current_time
                pending_plan = None
                print(f"Applied queued plan at safe cycle boundary near {current_time + 1}s.")
            previous_phase = phase

        final_time = traci.simulation.getTime()
        if abs(final_time - SIMULATION_END) > 1e-9:
            raise RuntimeError(f"SUMO ended at {final_time}, expected {SIMULATION_END}.")
    finally:
        if traci.isLoaded():
            traci.close()

    write_decisions(decisions)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    log_path.unlink(missing_ok=True)
    route_warnings = "Route file should be sorted" in log_text
    if route_warnings:
        raise RuntimeError("SUMO reported route-order warnings.")
    if file_hash(BASELINE_TRIPINFO_PATH) != baseline_hash:
        raise RuntimeError("The baseline tripinfo file was modified.")
    if not FLOWN_TRIPINFO_PATH.exists():
        raise RuntimeError("FlowSense tripinfo output was not created.")
    if not DECISIONS_PATH.exists():
        raise RuntimeError("FlowSense decision log was not created.")

    print(f"Simulation reached: {SIMULATION_END}s")
    print(f"Route vehicle count verified: {route_vehicle_count()}")
    print("Route-order warnings: 0")
    print("Baseline tripinfo modified: no")
    print(f"FlowSense tripinfo: {FLOWN_TRIPINFO_PATH}")
    print(f"Decision log: {DECISIONS_PATH}")


if __name__ == "__main__":
    main()
