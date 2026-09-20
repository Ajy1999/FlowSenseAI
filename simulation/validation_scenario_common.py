"""Shared, frozen methodology for validation scenarios 3 through 7."""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import median
from xml.etree import ElementTree

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SIM = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed" / "traffic_cleaned.csv"
SUMO = Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe")
SUMO_TOOLS = Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")
PHASE_STATES = (
    "GGggrrrrGGggrrrr", "yyyyrrrryyyyrrrr", "rrrrrrrrrrrrrrrr",
    "rrrrGGggrrrrGGgg", "rrrryyyyrrrryyyy", "rrrrrrrrrrrrrrrr",
)
SCENARIOS = {
    3: {"intersection_id": "INT-RING-01", "start": "2026-09-14 08:15:00", "weather": "clear"},
    4: {"intersection_id": "INT-EXPO-S", "start": "2026-09-14 09:00:00", "weather": "clear"},
    5: {"intersection_id": "INT-EXPO-E", "start": "2026-09-17 05:30:00", "weather": "cloudy"},
    6: {"intersection_id": "INT-RING-01", "start": "2026-09-18 07:15:00", "weather": "light_rain"},
    7: {"intersection_id": "INT-EXPO-N", "start": "2026-09-19 12:00:00", "weather": "clear"},
}
APPROACHES = ("N", "E", "S", "W")
ROUTES = {
    "N": ("route_north_to_south", "north_in south_out"),
    "S": ("route_south_to_north", "south_in north_out"),
    "E": ("route_east_to_west", "east_in west_out"),
    "W": ("route_west_to_east", "west_in east_out"),
}


def scenario_info(number: int) -> dict[str, object]:
    info = dict(SCENARIOS[number])
    info["start_ts"] = pd.Timestamp(info["start"], tz="UTC")
    info["end_ts"] = info["start_ts"] + pd.Timedelta(hours=1)
    frame = pd.read_csv(DATA)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    selected = frame[
        (frame["intersection_id"] == info["intersection_id"])
        & (frame["timestamp_utc"] >= info["start_ts"])
        & (frame["timestamp_utc"] < info["end_ts"])
    ].copy()
    if len(selected) != 16:
        raise ValueError(f"Scenario {number} does not contain exactly 16 rows.")
    if sorted(selected["timestamp_utc"].unique()) != list(
        pd.date_range(info["start_ts"], periods=4, freq="15min", tz="UTC")
    ):
        raise ValueError(f"Scenario {number} does not contain four consecutive intervals.")
    if any(set(g["approach"]) != set(APPROACHES) for _, g in selected.groupby("timestamp_utc")):
        raise ValueError(f"Scenario {number} is missing an approach.")
    counts = selected.groupby("approach")["vehicle_count_15min"].sum().reindex(APPROACHES)
    info.update(
        {
            "name": selected["intersection_name"].iloc[0],
            "weather_actual": selected["weather"].mode().iloc[0],
            "is_rush_hour": int(selected["is_rush_hour"].max()),
            "counts": {a: int(counts[a]) for a in APPROACHES},
            "total_demand": int(counts.sum()),
            "selected": selected,
        }
    )
    if info["weather_actual"] != info["weather"]:
        raise ValueError(f"Scenario {number} weather mismatch.")
    return info


def paths(number: int) -> dict[str, Path]:
    return {
        "route": SIM / f"dataset_routes_scenario{number}.rou.xml",
        "config": SIM / f"flowsense_dataset_baseline_scenario{number}.sumocfg",
        "baseline": SIM / f"dataset_baseline_scenario{number}_tripinfo.xml",
        "flowsense": SIM / f"dataset_flowsense_scenario{number}_tripinfo.xml",
        "decisions": SIM / f"flowsense_scenario{number}_signal_decisions.csv",
    }


def write_routes(number: int, info: dict[str, object]) -> None:
    records = []
    serial = 0
    for row in info["selected"].sort_values(["timestamp_utc", "approach"]).itertuples(index=False):
        count = int(row.vehicle_count_15min)
        interval = (row.timestamp_utc - info["start_ts"]).total_seconds()
        spacing = 900 / count if count else 900
        for i in range(count):
            records.append(
                {
                    "id": f"scenario{number}_vehicle_{serial:04d}",
                    "type": "flowsense_car",
                    "route": ROUTES[row.approach][0],
                    "depart": f"{interval + (i + 0.5) * spacing:.3f}",
                }
            )
            serial += 1
    records.sort(key=lambda r: float(r["depart"]))
    departures = [float(r["depart"]) for r in records]
    if departures != sorted(departures) or len(records) != info["total_demand"]:
        raise RuntimeError(f"Scenario {number} route validation failed.")
    root = ElementTree.Element("routes")
    ElementTree.SubElement(root, "vType", {"id": "flowsense_car", "accel": "2.6", "decel": "4.5", "sigma": "0.5", "length": "5.0", "minGap": "2.5", "maxSpeed": "13.89", "guiShape": "passenger"})
    for route_id, edges in ROUTES.values():
        ElementTree.SubElement(root, "route", {"id": route_id, "edges": edges})
    for record in records:
        ElementTree.SubElement(root, "vehicle", record)
    ElementTree.indent(root, space="    ")
    ElementTree.ElementTree(root).write(paths(number)["route"], encoding="UTF-8", xml_declaration=True)
    info["generated_departures"] = departures


def write_config(number: int) -> None:
    p = paths(number)
    p["config"].write_text(
        f"""<configuration>
    <input><net-file value="network.net.xml"/><route-files value="{p['route'].name}"/></input>
    <time><begin value="0"/><end value="3600"/><step-length value="1"/></time>
    <processing><time-to-teleport value="-1"/></processing>
    <output><tripinfo-output value="{p['baseline'].name}"/></output>
    <report><verbose value="true"/><no-step-log value="true"/></report>
</configuration>
""",
        encoding="utf-8",
    )


def run_baseline(number: int) -> str:
    p = paths(number)
    result = subprocess.run(
        [str(SUMO), "-c", p["config"].name],
        cwd=SIM,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0 or "Simulation ended at time: 3600.00." not in output:
        raise RuntimeError(f"Scenario {number} baseline failed:\n{output}")
    if "Route file should be sorted" in output or not p["baseline"].exists():
        raise RuntimeError(f"Scenario {number} baseline route/output validation failed.")
    return output


def load_controller():
    controller_path = ROOT / "src" / "flowsense" / "controller.py"
    spec = importlib.util.spec_from_file_location("flowsense_validation_controller", controller_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {controller_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_phase_controller


def run_flowsense(number: int, info: dict[str, object]) -> str:
    sys.path.insert(0, str(SUMO_TOOLS))
    import traci

    p = paths(number)
    plans = {}
    controller = load_controller()
    for update in (0, 900, 1800, 2700):
        timestamp = info["start_ts"] + pd.Timedelta(seconds=update)
        rows = info["selected"][info["selected"]["timestamp_utc"] == timestamp]
        result = controller(rows)
        if len(result) != 1:
            raise ValueError("Controller did not return one plan.")
        plans[update] = result.iloc[0]

    def apply(plan):
        phases = [
            traci.trafficlight.Phase(int(plan["ns_green_sec"]), PHASE_STATES[0]),
            traci.trafficlight.Phase(3, PHASE_STATES[1]),
            traci.trafficlight.Phase(1, PHASE_STATES[2]),
            traci.trafficlight.Phase(int(plan["ew_green_sec"]), PHASE_STATES[3]),
            traci.trafficlight.Phase(3, PHASE_STATES[4]),
            traci.trafficlight.Phase(1, PHASE_STATES[5]),
        ]
        logic = traci.trafficlight.Logic(f"flowsense-scenario{number}", 0, 0, phases, {})
        traci.trafficlight.setProgramLogic("junction_0", logic)
        traci.trafficlight.setPhase("junction_0", 0)

    def row(time, plan):
        return {
            "simulation_time": time,
            "dataset_timestamp": (info["start_ts"] + pd.Timedelta(seconds=time)).isoformat(),
            "ns_pressure": plan["ns_pressure"], "ew_pressure": plan["ew_pressure"],
            "ns_green_sec": plan["ns_green_sec"], "ew_green_sec": plan["ew_green_sec"],
            "yellow_sec": plan["yellow_sec"], "all_red_sec": plan["all_red_sec"],
            "selected_phase": plan["selected_phase"], "decision_reason": plan["decision_reason"],
        }

    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as log:
        log_path = Path(log.name)
    command = [str(SUMO), "-n", str(SIM / "network.net.xml"), "-r", str(p["route"]),
               "--begin", "0", "--end", "3600", "--step-length", "1",
               "--time-to-teleport", "-1", "--tripinfo-output", str(p["flowsense"]),
               "--log", str(log_path)]
    decisions = []
    pending = None
    applied_time = 0
    previous_phase = None
    try:
        traci.start(command)
        if "junction_0" not in traci.trafficlight.getIDList():
            raise RuntimeError("junction_0 is unavailable.")
        apply(plans[0])
        active = plans[0]
        decisions.append(row(0, plans[0]))
        for _ in range(3600):
            now = int(round(traci.simulation.getTime()))
            if now in plans and now != applied_time:
                pending = plans[now]
                decisions.append(row(now, pending))
            traci.simulationStep()
            phase = traci.trafficlight.getPhase("junction_0")
            if pending is not None and previous_phase == 5 and phase == 0:
                apply(pending)
                active = pending
                applied_time = now
                pending = None
            previous_phase = phase
        if abs(traci.simulation.getTime() - 3600) > 1e-9:
            raise RuntimeError("FlowSense did not reach 3600 seconds.")
    finally:
        if traci.isLoaded():
            traci.close()
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    log_path.unlink(missing_ok=True)
    if "Route file should be sorted" in log_text or not p["flowsense"].exists():
        raise RuntimeError(f"Scenario {number} FlowSense output validation failed.")
    with p["decisions"].open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(decisions[0]))
        writer.writeheader()
        writer.writerows(decisions)
    if len(decisions) != 4:
        raise RuntimeError(f"Scenario {number} requires four decisions.")
    return log_text


def read_trips(path: Path) -> list[dict[str, float]]:
    root = ElementTree.parse(path).getroot()
    trips = []
    for trip in root.findall("tripinfo"):
        trips.append({
            "duration": float(trip.get("duration", 0)),
            "waitingTime": float(trip.get("waitingTime", 0)),
            "timeLoss": float(trip.get("timeLoss", 0)),
            "stops": float(trip.get("waitingCount", 0)),
        })
    if not trips:
        raise ValueError(f"No trips in {path}")
    return trips


def percentile(values: list[float], rank: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * rank / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def calculate(trips: list[dict[str, float]]) -> dict[str, float]:
    travel = [x["duration"] for x in trips]
    waiting = [x["waitingTime"] for x in trips]
    loss = [x["timeLoss"] for x in trips]
    stops = [x["stops"] for x in trips]
    return {
        "completed": float(len(trips)),
        "avg_travel": sum(travel) / len(travel), "median_travel": median(travel),
        "p95_travel": percentile(travel, 95),
        "avg_waiting": sum(waiting) / len(waiting), "median_waiting": median(waiting),
        "p95_waiting": percentile(waiting, 95),
        "avg_loss": sum(loss) / len(loss), "avg_stops": sum(stops) / len(stops),
        "max_waiting": max(waiting), "max_travel": max(travel),
        "throughput": float(len(trips)),
    }
