"""Run the existing FlowSense controller on the isolated scenario-2 demand."""

from __future__ import annotations

import csv
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
TRIPINFO_PATH = SIMULATION_DIR / "dataset_flowsense_scenario2_tripinfo.xml"
DECISIONS_PATH = SIMULATION_DIR / "flowsense_scenario2_signal_decisions.csv"
TLS_ID = "junction_0"
INTERSECTION_ID = "INT-EXPO-N"
SIMULATION_START = pd.Timestamp("2026-09-13 10:00:00", tz="UTC")
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
    tools = Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")
    if not (tools / "traci").exists():
        raise FileNotFoundError(f"SUMO TraCI package was not found at {tools}")
    sys.path.insert(0, str(tools))


def load_controller():
    controller_path = PROJECT_ROOT / "src" / "flowsense" / "controller.py"
    spec = importlib.util.spec_from_file_location("flowsense_controller_scenario2", controller_path)
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
    return traci.trafficlight.Logic("flowsense-scenario2", 0, 0, phases, {})


def apply_plan(traci, plan: pd.Series) -> None:
    logic = build_logic(traci, int(plan["ns_green_sec"]), int(plan["ew_green_sec"]))
    traci.trafficlight.setProgramLogic(TLS_ID, logic)
    traci.trafficlight.setPhase(TLS_ID, 0)


def route_count() -> int:
    return len(ElementTree.parse(ROUTE_PATH).getroot().findall("vehicle"))


def write_decisions(rows: list[dict[str, object]]) -> None:
    fields = [
        "simulation_time", "dataset_timestamp", "ns_pressure", "ew_pressure",
        "ns_green_sec", "ew_green_sec", "yellow_sec", "all_red_sec",
        "selected_phase", "decision_reason",
    ]
    with DECISIONS_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    add_sumopath()
    import traci

    run_phase_controller = load_controller()
    observations = load_observations()
    expected = route_count()
    if expected != 601:
        raise ValueError(f"Expected 601 scenario-2 vehicles, found {expected}.")
    plans = {}
    for update_time, rows in observations.items():
        result = run_phase_controller(rows)
        if len(result) != 1:
            raise ValueError("The phase controller must return one plan per update.")
        plans[update_time] = result.iloc[0]

    print(f"TLS ID: {TLS_ID}")
    print(f"Route file: {ROUTE_PATH}")
    print(f"Expected vehicle count: {expected}")
    sumo_binary = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe"
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as log_file:
        log_path = Path(log_file.name)
    command = [
        sumo_binary, "-n", str(NETWORK_PATH), "-r", str(ROUTE_PATH),
        "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1",
        "--time-to-teleport", "-1", "--tripinfo-output", str(TRIPINFO_PATH),
        "--log", str(log_path),
    ]
    decisions = []
    pending_plan = None
    applied_plan_time = None
    previous_phase = None
    try:
        traci.start(command)
        print(f"SUMO version: {traci.getVersion()[1]}")
        if TLS_ID not in traci.trafficlight.getIDList():
            raise RuntimeError(f"TLS {TLS_ID} was not found in SUMO.")
        apply_plan(traci, plans[0])
        applied_plan_time = 0
        decisions.append(_decision_row(0, plans[0]))
        print_decision(0, plans[0])
        for _ in range(SIMULATION_END):
            current_time = int(round(traci.simulation.getTime()))
            if current_time in plans and current_time != applied_plan_time:
                pending_plan = plans[current_time]
                decisions.append(_decision_row(current_time, pending_plan))
                print(f"Queued scenario-2 FlowSense decision at {current_time}s")
                print_decision(current_time, pending_plan)
            traci.simulationStep()
            phase = traci.trafficlight.getPhase(TLS_ID)
            if pending_plan is not None and previous_phase == 5 and phase == 0:
                apply_plan(traci, pending_plan)
                applied_plan_time = current_time
                pending_plan = None
                print(f"Applied queued plan at safe boundary near {current_time + 1}s.")
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
    if "Route file should be sorted" in log_text:
        raise RuntimeError("SUMO reported route-order warnings.")
    if not TRIPINFO_PATH.exists():
        raise RuntimeError("Scenario-2 FlowSense tripinfo was not created.")
    if len(decisions) != 4:
        raise RuntimeError(f"Expected four decisions, found {len(decisions)}.")
    print(f"Simulation reached: {SIMULATION_END}s")
    print(f"Route vehicle count verified: {route_count()}")
    print("Route-order warnings: 0")
    print(f"Completed trips: {len(ElementTree.parse(TRIPINFO_PATH).getroot().findall('tripinfo'))}")
    print(f"FlowSense tripinfo: {TRIPINFO_PATH}")
    print(f"Decision log: {DECISIONS_PATH}")


def _decision_row(simulation_time: int, plan: pd.Series) -> dict[str, object]:
    return {
        "simulation_time": simulation_time,
        "dataset_timestamp": (SIMULATION_START + pd.Timedelta(seconds=simulation_time)).isoformat(),
        "ns_pressure": plan["ns_pressure"],
        "ew_pressure": plan["ew_pressure"],
        "ns_green_sec": plan["ns_green_sec"],
        "ew_green_sec": plan["ew_green_sec"],
        "yellow_sec": plan["yellow_sec"],
        "all_red_sec": plan["all_red_sec"],
        "selected_phase": plan["selected_phase"],
        "decision_reason": plan["decision_reason"],
    }


def print_decision(simulation_time: int, plan: pd.Series) -> None:
    print(
        f"FlowSense decision at {simulation_time}s: "
        f"NS={plan['ns_green_sec']}s, EW={plan['ew_green_sec']}s, "
        f"phase={plan['selected_phase']}"
    )


if __name__ == "__main__":
    main()
