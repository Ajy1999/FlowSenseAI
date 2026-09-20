"""Generate SUMO routes from one cleaned-dataset intersection and time window.

This first data-to-SUMO connection uses exact observed 15-minute vehicle
counts. Every approach is represented as straight-through traffic because the
dataset does not contain turn or origin-destination information.
"""

from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "traffic_cleaned.csv"
OUTPUT_PATH = Path(__file__).resolve().parent / "dataset_routes.rou.xml"

INTERSECTION_ID = "INT-EXPO-E"
WINDOW_START = pd.Timestamp("2026-09-17 09:00:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-09-17 10:00:00", tz="UTC")
INTERVAL_SECONDS = 15 * 60

ROUTE_MAPPING = {
    "N": ("north_in south_out", "route_north_to_south"),
    "S": ("south_in north_out", "route_south_to_north"),
    "E": ("east_in west_out", "route_east_to_west"),
    "W": ("west_in east_out", "route_west_to_east"),
}


def load_selected_data() -> pd.DataFrame:
    """Load and filter the requested intersection and UTC time window."""
    frame = pd.read_csv(DATA_PATH)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    selected = frame[
        (frame["intersection_id"] == INTERSECTION_ID)
        & (frame["timestamp_utc"] >= WINDOW_START)
        & (frame["timestamp_utc"] < WINDOW_END)
    ].copy()

    if set(selected["approach"].unique()) != set(ROUTE_MAPPING):
        raise ValueError("Selected data must contain exactly the N, E, S, and W approaches.")
    if selected["vehicle_count_15min"].isna().any():
        raise ValueError("Selected vehicle counts contain null values.")
    if (selected["vehicle_count_15min"] < 0).any():
        raise ValueError("Vehicle counts cannot be negative.")
    return selected.sort_values(["timestamp_utc", "approach"]).reset_index(drop=True)


def build_vehicle_records(frame: pd.DataFrame) -> list[dict[str, str]]:
    """Expand each 15-minute count into evenly spaced SUMO vehicle departures."""
    records: list[dict[str, str]] = []
    vehicle_number = 0

    for row in frame.itertuples(index=False):
        count = int(row.vehicle_count_15min)
        _, route_id = ROUTE_MAPPING[row.approach]
        interval_start = row.timestamp_utc
        seconds_between_departures = (
            INTERVAL_SECONDS / count if count else INTERVAL_SECONDS
        )

        for index in range(count):
            depart_seconds = (
                (interval_start - WINDOW_START).total_seconds()
                + (index + 0.5) * seconds_between_departures
            )
            records.append(
                {
                    "id": f"dataset_vehicle_{vehicle_number:04d}",
                    "type": "flowsense_car",
                    "route": route_id,
                    "depart": f"{depart_seconds:.3f}",
                }
            )
            vehicle_number += 1

    records.sort(key=lambda record: float(record["depart"]))
    departure_times = [float(record["depart"]) for record in records]
    if departure_times != sorted(departure_times):
        raise RuntimeError("Generated departure times are not globally sorted.")
    return records


def write_sumocfg_routes(vehicle_records: list[dict[str, str]]) -> None:
    """Write the dataset-derived routes to a new SUMO route XML file."""
    routes = ElementTree.Element("routes")
    ElementTree.SubElement(
        routes,
        "vType",
        {
            "id": "flowsense_car",
            "accel": "2.6",
            "decel": "4.5",
            "sigma": "0.5",
            "length": "5.0",
            "minGap": "2.5",
            "maxSpeed": "13.89",
            "guiShape": "passenger",
        },
    )

    for _, route_id in ROUTE_MAPPING.values():
        approach = next(
            approach for approach, value in ROUTE_MAPPING.items() if value[1] == route_id
        )
        edges = ROUTE_MAPPING[approach][0]
        ElementTree.SubElement(routes, "route", {"id": route_id, "edges": edges})

    for record in vehicle_records:
        ElementTree.SubElement(routes, "vehicle", record)

    ElementTree.indent(routes, space="    ")
    ElementTree.ElementTree(routes).write(
        OUTPUT_PATH,
        encoding="UTF-8",
        xml_declaration=True,
    )


def main() -> None:
    """Print selection checks, then write the dataset-derived SUMO routes."""
    selected = load_selected_data()
    counts = selected.groupby("approach")["vehicle_count_15min"].sum().reindex(
        ["N", "E", "S", "W"], fill_value=0
    )
    total_vehicle_count = int(counts.sum())

    print(f"Rows selected: {len(selected)}")
    print("Vehicle counts by approach:")
    for approach, count in counts.items():
        print(f"  {approach}: {int(count)}")
    print(f"Total vehicle count: {total_vehicle_count}")

    vehicle_records = build_vehicle_records(selected)
    if len(vehicle_records) != total_vehicle_count:
        raise RuntimeError("Generated vehicle count does not match the dataset count.")
    departure_times = [float(record["depart"]) for record in vehicle_records]
    if any(
        earlier > later
        for earlier, later in zip(departure_times, departure_times[1:])
    ):
        raise RuntimeError("Generated departure times are not monotonically non-decreasing.")

    write_sumocfg_routes(vehicle_records)
    print("First 10 departure times:")
    print(", ".join(f"{time:.3f}" for time in departure_times[:10]))
    print("Last 10 departure times:")
    print(", ".join(f"{time:.3f}" for time in departure_times[-10:]))
    print("Departure times globally sorted: yes")
    print(f"Wrote SUMO routes: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
