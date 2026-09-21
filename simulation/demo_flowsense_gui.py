"""Presentation-only reactive FlowSense Scenario 1 SUMO-GUI demo."""

from __future__ import annotations

import csv
import importlib.util
import tkinter as tk
import sys
import threading
from queue import Empty, Queue
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

from demo_common import DemoPanel, SIMULATION_END, SUMO_GUI, TLS_ID, configure_view, ensure_demo_inputs, output_paths, route_vehicle_count

ROOT = Path(__file__).resolve().parents[1]
SIM = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed" / "traffic_cleaned.csv"
NETWORK = SIM / "network.net.xml"
ROUTES = SIM / "dataset_routes.rou.xml"
OUTPUT = SIM / "demo_outputs" / "reactive"
START = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")
UPDATES = (0, 900, 1800, 2700)
PHASE_STATES = ("GGggrrrrGGggrrrr", "yyyyrrrryyyyrrrr", "rrrrrrrrrrrrrrrr", "rrrrGGggrrrrGGgg", "rrrryyyyrrrryyyy", "rrrrrrrrrrrrrrrr")


def load_controller():
    spec = importlib.util.spec_from_file_location("demo_reactive_controller", ROOT / "src" / "flowsense" / "controller.py")
    if spec is None or spec.loader is None:
        raise ImportError("Could not load the existing FlowSense controller.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_phase_controller


def load_observations() -> dict[int, pd.DataFrame]:
    frame = pd.read_csv(DATA)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    selected = frame[(frame["intersection_id"] == "INT-EXPO-E") & (frame["timestamp_utc"] >= START) & (frame["timestamp_utc"] < START + pd.Timedelta(hours=1))]
    result = {}
    for offset in UPDATES:
        rows = selected[selected["timestamp_utc"] == START + pd.Timedelta(seconds=offset)]
        if len(rows) != 4:
            raise ValueError(f"Expected four approaches at update {offset}s.")
        result[offset] = rows.copy()
    return result


def publish(panel_queue: Queue, lines: list[str]) -> None:
    panel_queue.put(("update", lines))


def metrics(tripinfo: Path) -> dict[str, float]:
    trips = list(ElementTree.parse(tripinfo).getroot().findall("tripinfo"))
    if not trips:
        raise ValueError(f"No completed trips found in {tripinfo}")
    travel = [float(row.get("duration", 0)) for row in trips]
    waiting = [float(row.get("waitingTime", 0)) for row in trips]
    ordered_wait = sorted(waiting)
    ordered_travel = sorted(travel)
    def p95(values):
        position = (len(values) - 1) * 0.95
        low = int(position)
        high = min(low + 1, len(values) - 1)
        return values[low] + (values[high] - values[low]) * (position - low)
    return {"completed": len(trips), "travel": sum(travel) / len(travel), "waiting": sum(waiting) / len(waiting), "p95_waiting": p95(ordered_wait), "p95_travel": p95(ordered_travel)}


def main() -> None:
    ensure_demo_inputs(NETWORK, ROUTES)
    expected = route_vehicle_count(ROUTES)
    sys.path.insert(0, str(Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")))
    import traci

    run_controller = load_controller()
    plans = {}
    for offset, rows in load_observations().items():
        plan = run_controller(rows)
        if len(plan) != 1:
            raise ValueError("The existing controller returned an invalid plan.")
        plans[offset] = plan.iloc[0]
    tripinfo, log = output_paths(OUTPUT, "reactive_presentation")
    decisions = OUTPUT / "reactive_presentation_decisions.csv"
    initial = plans[0]
    panel = DemoPanel("FlowSense AI - Reactive", ["FLOWSENSE REACTIVE", "Simulation time: 0000 / 3600 s", f"Vehicles: 0 / {expected}", "Control: Reactive", "NS pressure: 0.00", "EW pressure: 0.00", "NS green allocation: 0 s", "EW green allocation: 0 s", "Current phase: starting", "Decision: CURRENT TRAFFIC", "", "Simulation running..."])
    panel_queue: Queue = Queue()
    command = [str(SUMO_GUI), "-n", str(NETWORK), "-r", str(ROUTES), "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1", "--time-to-teleport", "-1", "--tripinfo-output", str(tripinfo), "--log", str(log)]

    def apply(traci_connection, plan):
        phases = [traci_connection.trafficlight.Phase(int(plan["ns_green_sec"]), PHASE_STATES[0]), traci_connection.trafficlight.Phase(3, PHASE_STATES[1]), traci_connection.trafficlight.Phase(1, PHASE_STATES[2]), traci_connection.trafficlight.Phase(int(plan["ew_green_sec"]), PHASE_STATES[3]), traci_connection.trafficlight.Phase(3, PHASE_STATES[4]), traci_connection.trafficlight.Phase(1, PHASE_STATES[5])]
        traci_connection.trafficlight.setProgramLogic(TLS_ID, traci_connection.trafficlight.Logic("demo-reactive", 0, 0, phases, {}))
        traci_connection.trafficlight.setPhase(TLS_ID, 0)

    def run_simulation() -> None:
        decision_rows = []
        departed = 0
        pending = None
        pending_time = None
        applied = 0
        previous_phase = None
        final_time = None
        try:
            traci.start(command)
            configure_view(traci)
            apply(traci, initial)
            while traci.simulation.getTime() < SIMULATION_END:
                now = int(round(traci.simulation.getTime()))
                visible = plans[now] if now in plans else plans[applied]
                phase = traci.trafficlight.getPhase(TLS_ID)
                names = ("NS GREEN", "NS YELLOW", "ALL RED", "EW GREEN", "EW YELLOW", "ALL RED")
                publish(panel_queue, ["FLOWSENSE REACTIVE", f"Simulation time: {now:04d} / 3600 s", f"Vehicles: {departed} / {expected}", "Control: Reactive", f"NS pressure: {float(visible['ns_pressure']):.2f}", f"EW pressure: {float(visible['ew_pressure']):.2f}", f"NS green allocation: {int(visible['ns_green_sec'])} s", f"EW green allocation: {int(visible['ew_green_sec'])} s", f"Current phase: {names[phase] if phase < len(names) else phase}", "Decision: CURRENT TRAFFIC", "", "Simulation running..."])
                if now in plans and now != applied:
                    pending = plans[now]
                    pending_time = now
                    decision_rows.append({"simulation_time": now, **{key: pending[key] for key in ("ns_pressure", "ew_pressure", "ns_green_sec", "ew_green_sec", "yellow_sec", "all_red_sec", "selected_phase", "decision_reason")}})
                traci.simulationStep()
                departed += traci.simulation.getDepartedNumber()
                current_phase = traci.trafficlight.getPhase(TLS_ID)
                if pending is not None and previous_phase == 5 and current_phase == 0:
                    apply(traci, pending)
                    applied = pending_time
                    pending = None
                    pending_time = None
                previous_phase = current_phase
            final_time = traci.simulation.getTime()
            if traci.isLoaded():
                traci.close()
            with decisions.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["simulation_time", "ns_pressure", "ew_pressure", "ns_green_sec", "ew_green_sec", "yellow_sec", "all_red_sec", "selected_phase", "decision_reason"])
                writer.writeheader()
                writer.writerows(decision_rows)
            if final_time != SIMULATION_END:
                raise RuntimeError(f"Reactive demo ended at {final_time}s.")
            result = metrics(tripinfo)
            publish(panel_queue, ["FLOWSENSE REACTIVE", f"Simulation complete: {int(final_time)} / 3600 s", f"Completed vehicles: {int(result['completed'])}", "Decision: CURRENT TRAFFIC", "", f"Average travel time: {result['travel']:.3f} s", f"Average waiting time: {result['waiting']:.3f} s", f"95th percentile waiting: {result['p95_waiting']:.3f} s", f"95th percentile travel: {result['p95_travel']:.3f} s", "", "", ""])
            panel_queue.put(("done", final_time))
        except Exception as error:
            panel_queue.put(("error", error))
        finally:
            if traci.isLoaded():
                traci.close()

    def poll_panel() -> None:
        try:
            while True:
                event, payload = panel_queue.get_nowait()
                if event == "update":
                    panel.update(payload)
                elif event == "error":
                    panel.update(["FLOWSENSE REACTIVE", "Simulation error", str(payload), "", "No validation output was modified."])
                elif event == "done":
                    print(f"Reactive demo reached {payload}s; outputs: {OUTPUT}")
        except Empty:
            pass
        panel.root.after(100, poll_panel)

    worker = threading.Thread(target=run_simulation, name="flowsense-reactive-simulation", daemon=True)
    worker.start()
    panel.root.after(100, poll_panel)
    panel.root.mainloop()


if __name__ == "__main__":
    main()
