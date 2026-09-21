"""Presentation-only predictive FlowSense Scenario 1 SUMO-GUI demo."""

from __future__ import annotations

import csv
import importlib.util
import tkinter as tk
import sys
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

from demo_common import DemoPanel, SIMULATION_END, SUMO_GUI, TLS_ID, configure_view, ensure_demo_inputs, output_paths, route_vehicle_count

ROOT = Path(__file__).resolve().parents[1]
SIM = Path(__file__).resolve().parent
NETWORK = SIM / "network.net.xml"
ROUTES = SIM / "dataset_routes.rou.xml"
OUTPUT = SIM / "demo_outputs" / "predictive"
MODEL = ROOT / "outputs" / "ml_prediction" / "gradient_boosting_model.joblib"
HISTORY = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"
START = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")
UPDATES = (0, 900, 1800, 2700)
PHASE_STATES = ("GGggrrrrGGggrrrr", "yyyyrrrryyyyrrrr", "rrrrrrrrrrrrrrrr", "rrrrGGggrrrrGGgg", "rrrryyyyrrrryyyy", "rrrrrrrrrrrrrrrr")


def load_predictive():
    path = ROOT / "src" / "flowsense" / "predictive_controller.py"
    spec = importlib.util.spec_from_file_location("demo_predictive_controller", path)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load the existing predictive controller.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_update(panel: DemoPanel, lines: list[str]) -> None:
    try:
        panel.update(lines)
        panel.root.update()
    except tk.TclError:
        pass


def metrics(tripinfo: Path) -> dict[str, float]:
    trips = list(ElementTree.parse(tripinfo).getroot().findall("tripinfo"))
    if not trips:
        raise ValueError(f"No completed trips found in {tripinfo}")
    travel = [float(row.get("duration", 0)) for row in trips]
    waiting = [float(row.get("waitingTime", 0)) for row in trips]
    def p95(values):
        ordered = sorted(values)
        position = (len(ordered) - 1) * 0.95
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"completed": len(trips), "travel": sum(travel) / len(travel), "waiting": sum(waiting) / len(waiting), "p95_waiting": p95(waiting), "p95_travel": p95(travel)}


def main() -> None:
    ensure_demo_inputs(NETWORK, ROUTES)
    expected = route_vehicle_count(ROUTES)
    if not MODEL.exists() or not HISTORY.exists():
        raise FileNotFoundError("The predictive model or prediction history is missing.")
    sys.path.insert(0, str(Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")))
    import traci

    predictive = load_predictive()
    model = predictive.load_predictive_model(MODEL)
    history = predictive.load_prediction_history(HISTORY)
    plans = {}
    rows = {}
    for offset in UPDATES:
        timestamp = START + pd.Timedelta(seconds=offset)
        current, predicted = predictive.predict_next_demand(model, history, intersection_id="INT-EXPO-E", timestamp_utc=timestamp)
        plan, _ = predictive.run_predictive_phase_controller(model, history, intersection_id="INT-EXPO-E", timestamp_utc=timestamp)
        if len(plan) != 1 or len(predicted) != 4:
            raise ValueError("The existing predictive controller returned an invalid plan.")
        plans[offset] = plan.iloc[0]
        current_values = current.set_index("approach")["vehicle_count_15min"]
        values = predicted.set_index("approach")["vehicle_count_15min"]
        rows[offset] = {"simulation_time": offset, "current_N": float(current_values["N"]), "current_E": float(current_values["E"]), "current_S": float(current_values["S"]), "current_W": float(current_values["W"]), "predicted_N": float(values["N"]), "predicted_E": float(values["E"]), "predicted_S": float(values["S"]), "predicted_W": float(values["W"])}

    tripinfo, log = output_paths(OUTPUT, "predictive_presentation")
    decisions = OUTPUT / "predictive_presentation_decisions.csv"
    panel = DemoPanel("FlowSense AI - Predictive", ["FLOWSENSE PREDICTIVE", "Simulation time: 0000 / 3600 s", f"Vehicles: 0 / {expected}", "Control: Predictive", "Current NS/EW demand: --", "Predicted NS/EW demand: --", "NS pressure: 0.00 | EW pressure: 0.00", "NS green allocation: 0 s", "EW green allocation: 0 s", "Current phase: starting", "Decision: CURRENT + PREDICTION", "", "Simulation running..."])
    command = [str(SUMO_GUI), "-n", str(NETWORK), "-r", str(ROUTES), "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1", "--time-to-teleport", "-1", "--tripinfo-output", str(tripinfo), "--log", str(log)]
    pending = None
    pending_time = None
    applied = 0
    previous_phase = None
    departed = 0
    final_time = None
    decision_rows = []

    def apply(plan):
        phases = [traci.trafficlight.Phase(int(plan["ns_green_sec"]), PHASE_STATES[0]), traci.trafficlight.Phase(3, PHASE_STATES[1]), traci.trafficlight.Phase(1, PHASE_STATES[2]), traci.trafficlight.Phase(int(plan["ew_green_sec"]), PHASE_STATES[3]), traci.trafficlight.Phase(3, PHASE_STATES[4]), traci.trafficlight.Phase(1, PHASE_STATES[5])]
        traci.trafficlight.setProgramLogic(TLS_ID, traci.trafficlight.Logic("demo-predictive", 0, 0, phases, {}))
        traci.trafficlight.setPhase(TLS_ID, 0)

    try:
        traci.start(command)
        configure_view(traci)
        apply(plans[0])
        while traci.simulation.getTime() < SIMULATION_END:
            now = int(round(traci.simulation.getTime()))
            visible = plans[now] if now in plans else plans[applied]
            info = rows[applied]
            phase = traci.trafficlight.getPhase(TLS_ID)
            names = ("NS GREEN", "NS YELLOW", "ALL RED", "EW GREEN", "EW YELLOW", "ALL RED")
            safe_update(panel, ["FLOWSENSE PREDICTIVE", f"Simulation time: {now:04d} / 3600 s", f"Vehicles: {departed} / {expected}", "Control: Predictive", f"Current NS/EW demand: {info['current_N'] + info['current_S']:.1f} / {info['current_E'] + info['current_W']:.1f}", f"Predicted NS/EW demand: {info['predicted_N'] + info['predicted_S']:.1f} / {info['predicted_E'] + info['predicted_W']:.1f}", f"NS pressure: {float(visible['ns_pressure']):.2f} | EW pressure: {float(visible['ew_pressure']):.2f}", f"NS green allocation: {int(visible['ns_green_sec'])} s", f"EW green allocation: {int(visible['ew_green_sec'])} s", f"Current phase: {names[phase] if phase < len(names) else phase}", "Decision: CURRENT + PREDICTION", "", "Simulation running..."])
            if now in plans and now != applied:
                pending = plans[now]
                pending_time = now
                info = rows[now]
                decision_rows.append({"simulation_time": now, **info, "ns_pressure": pending["ns_pressure"], "ew_pressure": pending["ew_pressure"], "ns_green_sec": pending["ns_green_sec"], "ew_green_sec": pending["ew_green_sec"], "selected_phase": pending["selected_phase"]})
            traci.simulationStep()
            departed += traci.simulation.getDepartedNumber()
            current_phase = traci.trafficlight.getPhase(TLS_ID)
            if pending is not None and previous_phase == 5 and current_phase == 0:
                apply(pending)
                applied = pending_time
                pending = None
                pending_time = None
            previous_phase = current_phase
        final_time = traci.simulation.getTime()
    finally:
        if traci.isLoaded():
            traci.close()
    with decisions.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=decision_rows[0].keys() if decision_rows else ["simulation_time"])
        writer.writeheader()
        writer.writerows(decision_rows)
    if final_time != SIMULATION_END:
        raise RuntimeError(f"Predictive demo ended at {final_time}s.")
    result = metrics(tripinfo)
    safe_update(panel, ["FLOWSENSE PREDICTIVE", f"Simulation complete: {int(final_time)} / 3600 s", f"Completed vehicles: {int(result['completed'])}", "Decision: CURRENT + PREDICTION", "", f"Average travel time: {result['travel']:.3f} s", f"Average waiting time: {result['waiting']:.3f} s", f"95th percentile waiting: {result['p95_waiting']:.3f} s", f"95th percentile travel: {result['p95_travel']:.3f} s", "", "", "", ""])
    print(f"Predictive demo reached {final_time}s; outputs: {OUTPUT}")


if __name__ == "__main__":
    main()
