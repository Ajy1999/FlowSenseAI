"""Generate the isolated scenario-2 SUMO demand from the cleaned dataset."""

from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "traffic_cleaned.csv"
OUTPUT_PATH = Path(__file__).resolve().parent / "dataset_routes_scenario2.rou.xml"

INTERSECTION_ID = "INT-EXPO-N"
WINDOW_START = pd.Timestamp("2026-09-13 10:00:00", tz="UTC")
WINDOW_END = pd.Timestamp("2026-09-13 11:00:00", tz="UTC")
INTERVAL_SECONDS = 900
APPROACHES = ("N", "E", "S", "W")
ROUTE_MAPPING = {
    "N": ("north_in south_out", "route_north_to_south"),
    "S": ("south_in north_out", "route_south_to_north"),
    "E": ("east_in west_out", "route_east_to_west"),
    "W": ("west_in east_out", "route_west_to_east"),
}


def load_selected_data() -> pd.DataFrame:
    frame = pd.read_csv(DATA_PATH)
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    selected = frame[
        (frame["intersection_id"] == INTERSECTION_ID)
        & (frame["timestamp_utc"] >= WINDOW_START)
        & (frame["timestamp_utc"] < WINDOW_END)
    ].copy()
    expected_timestamps = list(
        pd.date_range(WINDOW_START, periods=4, freq="15min", tz="UTC")
    )
    if sorted(selected["timestamp_utc"].unique()) != expected_timestamps:
        raise ValueError("Scenario 2 must contain four consecutive 15-minute timestamps.")
    if len(selected) != 16:
        raise ValueError(f"Expected 16 scenario rows, found {len(selected)}.")
    for timestamp, group in selected.groupby("timestamp_utc"):
        if set(group["approach"]) != set(APPROACHES):
            raise ValueError(f"Missing approach at {timestamp}.")
    if selected["vehicle_count_15min"].isna().any() or (
        selected["vehicle_count_15min"] < 0
    ).any():
        raise ValueError("Scenario 2 contains invalid vehicle counts.")
    return selected.sort_values(["timestamp_utc", "approach"]).reset_index(drop=True)


def build_vehicle_records(frame: pd.DataFrame) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    vehicle_number = 0
    for row in frame.itertuples(index=False):
        count = int(row.vehicle_count_15min)
        route_id = ROUTE_MAPPING[row.approach][1]
        interval_start = (row.timestamp_utc - WINDOW_START).total_seconds()
        spacing = INTERVAL_SECONDS / count if count else INTERVAL_SECONDS
        for index in range(count):
            departure = interval_start + (index + 0.5) * spacing
            records.append(
                {
                    "id": f"scenario2_vehicle_{vehicle_number:04d}",
                    "type": "flowsense_car",
                    "route": route_id,
                    "depart": f"{departure:.3f}",
                }
            )
            vehicle_number += 1
    records.sort(key=lambda record: float(record["depart"]))
    departures = [float(record["depart"]) for record in records]
    if any(a > b for a, b in zip(departures, departures[1:])):
        raise RuntimeError("Departure times are not monotonically non-decreasing.")
    return records


def write_routes(records: list[dict[str, str]]) -> None:
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
    for route_id, edges in (
        ("route_north_to_south", "north_in south_out"),
        ("route_south_to_north", "south_in north_out"),
        ("route_east_to_west", "east_in west_out"),
        ("route_west_to_east", "west_in east_out"),
    ):
        ElementTree.SubElement(routes, "route", {"id": route_id, "edges": edges})
    for record in records:
        ElementTree.SubElement(routes, "vehicle", record)
    ElementTree.indent(routes, space="    ")
    ElementTree.ElementTree(routes).write(
        OUTPUT_PATH, encoding="UTF-8", xml_declaration=True
    )


def main() -> None:
    selected = load_selected_data()
    print(f"Intersection: {INTERSECTION_ID}")
    print(f"Intersection name: {selected['intersection_name'].iloc[0]}")
    print(f"Start timestamp: {WINDOW_START.isoformat()}")
    print(f"End timestamp: {WINDOW_END.isoformat()}")
    print("Vehicle counts by interval:")
    for timestamp, group in selected.groupby("timestamp_utc"):
        counts = group.set_index("approach")["vehicle_count_15min"].reindex(APPROACHES)
        print(
            f"  {timestamp.isoformat()}: "
            + ", ".join(f"{approach}={int(counts[approach])}" for approach in APPROACHES)
        )
    total = int(selected["vehicle_count_15min"].sum())
    records = build_vehicle_records(selected)
    if len(records) != total:
        raise RuntimeError("Generated vehicle count does not match dataset demand.")
    print(f"Total vehicle demand: {total}")
    print(f"Generated vehicles: {len(records)}")
    departures = [float(record["depart"]) for record in records]
    print("First departure times:", ", ".join(f"{value:.3f}" for value in departures[:5]))
    print("Last departure times:", ", ".join(f"{value:.3f}" for value in departures[-5:]))
    print("Departure times globally sorted: yes")
    write_routes(records)
    print(f"Wrote: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
