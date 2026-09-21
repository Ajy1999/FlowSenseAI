"""Presentation-only fixed-time Scenario 1 SUMO-GUI demo."""

from __future__ import annotations

import tkinter as tk
import sys
from pathlib import Path
from statistics import median
from xml.etree import ElementTree

from demo_common import (
    DemoPanel,
    SIMULATION_END,
    SUMO_GUI,
    configure_view,
    ensure_demo_inputs,
    output_paths,
    route_vehicle_count,
)


SIM = Path(__file__).resolve().parent
NETWORK = SIM / "network.net.xml"
ROUTES = SIM / "dataset_routes.rou.xml"
OUTPUT = SIM / "demo_outputs" / "fixed"


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def metrics(tripinfo: Path) -> dict[str, float]:
    trips = list(ElementTree.parse(tripinfo).getroot().findall("tripinfo"))
    if not trips:
        raise ValueError(f"No completed trips found in {tripinfo}")
    travel = [float(row.get("duration", 0)) for row in trips]
    waiting = [float(row.get("waitingTime", 0)) for row in trips]
    return {
        "completed": len(trips),
        "travel": sum(travel) / len(travel),
        "waiting": sum(waiting) / len(waiting),
        "p95_waiting": percentile(waiting, 95),
        "p95_travel": percentile(travel, 95),
    }


def safe_update(panel: DemoPanel, lines: list[str]) -> bool:
    try:
        panel.update(lines)
        panel.root.update()
        return True
    except tk.TclError:
        return False


def phase_text(traci, now: float) -> tuple[str, float]:
    phase = traci.trafficlight.getPhase("junction_0")
    remaining = max(0.0, traci.trafficlight.getNextSwitch("junction_0") - now)
    names = ("NS GREEN", "NS YELLOW", "ALL RED", "EW GREEN", "EW YELLOW", "ALL RED")
    return names[phase] if phase < len(names) else f"PHASE {phase}", remaining


def main() -> None:
    ensure_demo_inputs(NETWORK, ROUTES)
    expected = route_vehicle_count(ROUTES)
    sys.path.insert(0, str(Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")))
    import traci

    tripinfo, log = output_paths(OUTPUT, "fixed_presentation")
    panel = DemoPanel(
        "FlowSense AI - Fixed Time",
        ["FIXED-TIME SIGNAL", "Simulation time: 0000 / 3600 s", f"Vehicles: 0 / {expected}", "Control: Fixed schedule", "Current phase: starting", "Phase remaining: --", "Current demand: unavailable", "Decision: PREDETERMINED", "", "Waiting for completion metrics..."],
    )
    command = [
        str(SUMO_GUI), "-n", str(NETWORK), "-r", str(ROUTES),
        "--begin", "0", "--end", str(SIMULATION_END), "--step-length", "1",
        "--time-to-teleport", "-1", "--tripinfo-output", str(tripinfo), "--log", str(log),
    ]
    departed = 0
    final_time = None
    try:
        traci.start(command)
        configure_view(traci)
        while traci.simulation.getTime() < SIMULATION_END:
            now = traci.simulation.getTime()
            phase, remaining = phase_text(traci, now)
            safe_update(panel, [
                "FIXED-TIME SIGNAL",
                f"Simulation time: {int(now):04d} / {SIMULATION_END} s",
                f"Vehicles: {departed} / {expected}",
                "Control: Fixed schedule",
                f"Current phase: {phase}",
                f"Phase remaining: {remaining:.0f} s",
                "Current demand: unavailable",
                "Decision: PREDETERMINED",
                "",
                "Simulation running...",
            ])
            traci.simulationStep()
            departed += traci.simulation.getDepartedNumber()
        final_time = traci.simulation.getTime()
    finally:
        if traci.isLoaded():
            traci.close()
    if final_time != SIMULATION_END:
        raise RuntimeError(f"Fixed demo ended at {final_time}s.")
    result = metrics(tripinfo)
    safe_update(panel, [
        "FIXED-TIME SIGNAL",
        f"Simulation complete: {int(final_time)} / {SIMULATION_END} s",
        f"Completed vehicles: {int(result['completed'])}",
        "Control: Fixed schedule",
        "Decision: PREDETERMINED",
        "",
        f"Average travel time: {result['travel']:.3f} s",
        f"Average waiting time: {result['waiting']:.3f} s",
        f"95th percentile waiting: {result['p95_waiting']:.3f} s",
        f"95th percentile travel: {result['p95_travel']:.3f} s",
    ])
    print(f"Fixed demo reached {final_time}s; outputs: {OUTPUT}")


if __name__ == "__main__":
    main()
