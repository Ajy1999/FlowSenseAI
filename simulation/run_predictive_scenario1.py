"""Run Predictive FlowSense for Scenario 1 without changing existing outputs."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SIMULATION_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "validation_predictive"
NETWORK_PATH = SIMULATION_DIR / "network.net.xml"
ROUTE_PATH = SIMULATION_DIR / "dataset_routes.rou.xml"
MODEL_PATH = ROOT / "outputs" / "ml_prediction" / "gradient_boosting_model.joblib"
HISTORY_PATH = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"
BASELINE_TRIPINFO = SIMULATION_DIR / "dataset_baseline_tripinfo.xml"
REACTIVE_TRIPINFO = SIMULATION_DIR / "dataset_flowsense_tripinfo.xml"
REACTIVE_DECISIONS = SIMULATION_DIR / "flowsense_signal_decisions.csv"
PREDICTIVE_TRIPINFO = OUTPUT_DIR / "predictive_scenario1_tripinfo.xml"
PREDICTIVE_DECISIONS = OUTPUT_DIR / "predictive_decision_log.csv"
SUMO_LOG = OUTPUT_DIR / "predictive_scenario1_sumo.log"

TLS_ID = "junction_0"
INTERSECTION_ID = "INT-EXPO-E"
SIMULATION_START = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")
UPDATE_TIMES = (0, 900, 1800, 2700)
SIMULATION_END = 3600
PHASE_STATES = (
    "GGggrrrrGGggrrrr", "yyyyrrrryyyyrrrr", "rrrrrrrrrrrrrrrr",
    "rrrrGGggrrrrGGgg", "rrrryyyyrrrryyyy", "rrrrrrrrrrrrrrrr",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_sumopath() -> None:
    tools = Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")
    if not (tools / "traci").exists():
        raise FileNotFoundError(f"SUMO TraCI package was not found at {tools}")
    sys.path.insert(0, str(tools))


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def route_vehicle_count() -> int:
    return len(ElementTree.parse(ROUTE_PATH).getroot().findall("vehicle"))


def build_phase_logic(traci, ns_green: int, ew_green: int):
    phases = [
        traci.trafficlight.Phase(ns_green, PHASE_STATES[0]),
        traci.trafficlight.Phase(3, PHASE_STATES[1]),
        traci.trafficlight.Phase(1, PHASE_STATES[2]),
        traci.trafficlight.Phase(ew_green, PHASE_STATES[3]),
        traci.trafficlight.Phase(3, PHASE_STATES[4]),
        traci.trafficlight.Phase(1, PHASE_STATES[5]),
    ]
    return traci.trafficlight.Logic("flowsense-predictive", 0, 0, phases, {})


def apply_plan(traci, plan: pd.Series) -> None:
    logic = build_phase_logic(traci, int(plan["ns_green_sec"]), int(plan["ew_green_sec"]))
    traci.trafficlight.setProgramLogic(TLS_ID, logic)
    traci.trafficlight.setPhase(TLS_ID, 0)


def write_decisions(rows: list[dict[str, object]]) -> None:
    columns = [
        "scenario", "simulation_time", "timestamp",
        "predicted_N", "predicted_E", "predicted_S", "predicted_W",
        "reactive/current_N", "reactive/current_E", "reactive/current_S",
        "reactive/current_W", "ns_pressure", "ew_pressure",
        "allocated_ns_green", "allocated_ew_green",
        "yellow_sec", "all_red_sec", "selected_phase", "decision_reason",
    ]
    with PREDICTIVE_DECISIONS.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictive = load_module(
        "predictive_controller_for_scenario1",
        ROOT / "src" / "flowsense" / "predictive_controller.py",
    )
    model = predictive.load_predictive_model(MODEL_PATH)
    history = predictive.load_prediction_history(HISTORY_PATH)
    protected_hashes = {
        path: file_hash(path)
        for path in (BASELINE_TRIPINFO, REACTIVE_TRIPINFO, REACTIVE_DECISIONS, ROUTE_PATH, NETWORK_PATH)
    }
    if route_vehicle_count() != 922:
        raise ValueError(f"Expected 922 route vehicles, found {route_vehicle_count()}.")

    plans: dict[int, pd.Series] = {}
    decision_rows: list[dict[str, object]] = []
    for update_time in UPDATE_TIMES:
        timestamp = SIMULATION_START + pd.Timedelta(seconds=update_time)
        plan, predicted = predictive.run_predictive_phase_controller(
            model, history, intersection_id=INTERSECTION_ID, timestamp_utc=timestamp
        )
        if len(plan) != 1 or len(predicted) != 4:
            raise ValueError("Predictive controller returned an invalid decision shape.")
        plans[update_time] = plan.iloc[0]
        current = predicted.set_index("approach")["vehicle_count_15min"]
        predicted_values = predicted.set_index("approach")["vehicle_count_15min"]
        source = history[
            (history["intersection_id"] == INTERSECTION_ID)
            & (history["timestamp_utc"] == timestamp)
        ].set_index("approach")["vehicle_count_15min"]
        decision_rows.append({
            "scenario": "Scenario 1",
            "simulation_time": update_time,
            "timestamp": timestamp.isoformat(),
            "predicted_N": float(predicted_values["N"]),
            "predicted_E": float(predicted_values["E"]),
            "predicted_S": float(predicted_values["S"]),
            "predicted_W": float(predicted_values["W"]),
            "reactive/current_N": float(source["N"]),
            "reactive/current_E": float(source["E"]),
            "reactive/current_S": float(source["S"]),
            "reactive/current_W": float(source["W"]),
            "ns_pressure": float(plan.iloc[0]["ns_pressure"]),
            "ew_pressure": float(plan.iloc[0]["ew_pressure"]),
            "allocated_ns_green": int(plan.iloc[0]["ns_green_sec"]),
            "allocated_ew_green": int(plan.iloc[0]["ew_green_sec"]),
            "yellow_sec": int(plan.iloc[0]["yellow_sec"]),
            "all_red_sec": int(plan.iloc[0]["all_red_sec"]),
            "selected_phase": plan.iloc[0]["selected_phase"],
            "decision_reason": plan.iloc[0]["decision_reason"],
        })

    add_sumopath()
    import traci

    sumo_binary = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe"
    sumo_cmd = [
        sumo_binary, "-n", str(NETWORK_PATH), "-r", str(ROUTE_PATH),
        "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1",
        "--time-to-teleport", "-1", "--tripinfo-output", str(PREDICTIVE_TRIPINFO),
        "--log", str(SUMO_LOG),
    ]
    pending_plan = None
    applied_plan_time = None
    previous_phase = None
    try:
        traci.start(sumo_cmd)
        if TLS_ID not in traci.trafficlight.getIDList():
            raise RuntimeError(f"TLS {TLS_ID} was not found in SUMO.")
        apply_plan(traci, plans[0])
        applied_plan_time = 0
        for simulation_time in range(SIMULATION_END):
            current_time = int(round(traci.simulation.getTime()))
            if current_time in plans and current_time != applied_plan_time:
                pending_plan = plans[current_time]
            traci.simulationStep()
            phase = traci.trafficlight.getPhase(TLS_ID)
            if pending_plan is not None and previous_phase == 5 and phase == 0:
                apply_plan(traci, pending_plan)
                applied_plan_time = current_time
                pending_plan = None
            previous_phase = phase
        final_time = traci.simulation.getTime()
        if abs(final_time - SIMULATION_END) > 1e-9:
            raise RuntimeError(f"SUMO ended at {final_time}, expected {SIMULATION_END}.")
    finally:
        if traci.isLoaded():
            traci.close()

    write_decisions(decision_rows)
    log_text = SUMO_LOG.read_text(encoding="utf-8", errors="replace")
    if "Route file should be sorted" in log_text:
        raise RuntimeError("SUMO reported route-order warnings.")
    error_lines = [
        line for line in log_text.splitlines()
        if line.startswith("Error:") or line.startswith("Fatal:")
    ]
    if error_lines:
        raise RuntimeError("SUMO log contains an error: " + " | ".join(error_lines))
    for path, expected_hash in protected_hashes.items():
        if file_hash(path) != expected_hash:
            raise RuntimeError(f"Protected file was modified: {path}")
    with PREDICTIVE_DECISIONS.open(newline="", encoding="utf-8") as decision_file:
        written_decisions = list(csv.DictReader(decision_file))
    if len(decision_rows) != 4 or len(written_decisions) != 4:
        raise RuntimeError("Predictive decision log must contain exactly four decisions.")
    print(f"Predictive Scenario 1 reached {SIMULATION_END}s.")
    print(f"Predictive tripinfo: {PREDICTIVE_TRIPINFO}")
    print(f"Predictive decision log: {PREDICTIVE_DECISIONS}")
    print("Protected existing files modified: no")
    print("Route-order warnings: 0")


if __name__ == "__main__":
    main()
