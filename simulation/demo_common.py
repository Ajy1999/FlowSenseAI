"""Shared presentation-only helpers for the isolated SUMO-GUI demos."""

from __future__ import annotations

import hashlib
import tkinter as tk
from pathlib import Path
from typing import Callable
from xml.etree import ElementTree


SUMO_GUI = Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo-gui.exe")
TLS_ID = "junction_0"
SIMULATION_END = 3600
ROUTE_VEHICLES = 922


class DemoPanel:
    """Small always-on-top presentation panel updated by the TraCI loop."""

    def __init__(self, title: str, lines: list[str]) -> None:
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg="#101820")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.labels: list[tk.Label] = []
        for index, line in enumerate(lines):
            label = tk.Label(
                self.root,
                text=line,
                anchor="w",
                justify="left",
                width= thirty_width(lines),
                padx=16,
                pady=5,
                bg="#101820",
                fg="#f2f5f7" if index else "#5eead4",
                font=("Segoe UI", 14 if index else 18, "bold" if index == 0 else "normal"),
            )
            label.pack(fill="x")
            self.labels.append(label)
        self.root.update_idletasks()

    def update(self, lines: list[str]) -> None:
        try:
            for label, line in zip(self.labels, lines):
                label.configure(text=line)
            self.root.update_idletasks()
        except tk.TclError:
            self.labels = []

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def thirty_width(lines: list[str]) -> int:
    return max(30, min(58, max((len(line) for line in lines), default=30) + 2))


def route_vehicle_count(route_path: Path) -> int:
    return len(ElementTree.parse(route_path).getroot().findall("vehicle"))


def ensure_demo_inputs(network_path: Path, route_path: Path) -> None:
    if not SUMO_GUI.exists():
        raise FileNotFoundError(f"SUMO-GUI was not found at {SUMO_GUI}")
    if not network_path.exists() or not route_path.exists():
        raise FileNotFoundError("The required Scenario 1 network or route file is missing.")
    count = route_vehicle_count(route_path)
    if count != ROUTE_VEHICLES:
        raise ValueError(f"Expected {ROUTE_VEHICLES} route vehicles, found {count}.")


def configure_view(traci) -> None:
    """Focus SUMO-GUI on the junction without changing the network."""
    for view_id in traci.gui.getIDList():
        traci.gui.setZoom(view_id, 220)
        traci.gui.setSchema(view_id, "real world")
        traci.gui.trackVehicle(view_id, "")


def run_with_panel(
    traci,
    panel: DemoPanel,
    update_panel: Callable[[float], list[str]],
    *,
    on_started: Callable[[], None] | None = None,
) -> float:
    """Advance a connected SUMO-GUI simulation while refreshing the panel."""
    if on_started is not None:
        on_started()
    configure_view(traci)
    previous_time = -1
    while traci.simulation.getTime() < SIMULATION_END:
        simulation_time = traci.simulation.getTime()
        if int(simulation_time) != previous_time:
            panel.update(update_panel(simulation_time))
            previous_time = int(simulation_time)
        traci.simulationStep()
        panel.root.update()
    final_time = traci.simulation.getTime()
    panel.update(update_panel(final_time))
    panel.root.update()
    return final_time


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def output_paths(output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{stem}_tripinfo.xml", output_dir / f"{stem}_sumo.log"
