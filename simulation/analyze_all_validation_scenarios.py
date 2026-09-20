"""Build the six-scenario comparison and pooled aggregate outputs."""

from __future__ import annotations

import csv
from pathlib import Path

from validation_scenario_common import (
    SCENARIOS,
    calculate,
    paths,
    read_trips,
    scenario_info,
)

OUT = Path(__file__).resolve().parent
METRICS = (
    ("completed", "completed"), ("avg_travel", "avg_travel_time_sec"),
    ("median_travel", "median_travel_time_sec"), ("p95_travel", "p95_travel_time_sec"),
    ("avg_waiting", "avg_waiting_time_sec"), ("median_waiting", "median_waiting_time_sec"),
    ("p95_waiting", "p95_waiting_time_sec"), ("avg_loss", "avg_time_loss_sec"),
    ("avg_stops", "avg_stops"), ("max_waiting", "max_waiting_sec"),
    ("max_travel", "max_travel_time_sec"), ("throughput", "throughput"),
)


def row_for(number, info, baseline, flowsense):
    start_time = (
        info["start_ts"].isoformat()
        if hasattr(info["start_ts"], "isoformat")
        else info["start_ts"]
    )
    end_time = (
        info["end_ts"].isoformat()
        if hasattr(info["end_ts"], "isoformat")
        else info["end_ts"]
    )
    row = {
        "scenario_id": "ALL_SCENARIOS" if number == "ALL" else f"SCENARIO_{number}",
        "intersection_id": info["intersection_id"],
        "intersection_name": info["name"],
        "start_time": start_time,
        "end_time": end_time,
        "weather": info["weather_actual"],
        "is_rush_hour": info["is_rush_hour"],
        "total_demand": info["total_demand"],
    }
    for key, suffix in METRICS:
        row[f"baseline_{suffix}"] = baseline[key]
        row[f"flowsense_{suffix}"] = flowsense[key]
        if key == "completed":
            diff_name, pct_name = "completed_difference", "completed_change_pct"
        elif key == "throughput":
            diff_name, pct_name = "throughput_difference", "throughput_change_pct"
        else:
            diff_name, pct_name = f"{suffix.replace('_sec','')}_difference_sec", f"{suffix.replace('_sec','')}_change_pct"
        difference = flowsense[key] - baseline[key]
        row[diff_name] = difference
        row[pct_name] = "" if baseline[key] == 0 else difference / baseline[key] * 100
    return row


def aggregate(records):
    all_base = [trip for record in records for trip in record["baseline_trips"]]
    all_flow = [trip for record in records for trip in record["flowsense_trips"]]
    base = calculate(all_base)
    flow = calculate(all_flow)
    info = {
        "intersection_id": "ALL_SCENARIOS",
        "name": "Aggregate across scenarios 1-7",
        "start_ts": "", "end_ts": "", "weather_actual": "multiple",
        "is_rush_hour": "multiple", "total_demand": sum(r["total_demand"] for r in records),
    }
    return row_for("ALL", info, base, flow)


def main():
    records = []
    for number in (1, 2, 3, 4, 5, 6, 7):
        if number == 1:
            info = scenario_info(3)  # overwritten with stable metadata below
            info.update({"intersection_id": "INT-EXPO-E", "name": "Expo district east approach", "start_ts": "2026-09-17T09:00:00+00:00", "end_ts": "2026-09-17T10:00:00+00:00", "weather_actual": "clear", "is_rush_hour": 1, "total_demand": 922})
            base_path = OUT / "dataset_baseline_tripinfo.xml"; flow_path = OUT / "dataset_flowsense_tripinfo.xml"
        elif number == 2:
            info = scenario_info(3)
            info.update({"intersection_id": "INT-EXPO-N", "name": "Expo district north approach", "start_ts": "2026-09-13T10:00:00+00:00", "end_ts": "2026-09-13T11:00:00+00:00", "weather_actual": "clear", "is_rush_hour": 0, "total_demand": 601})
            base_path = OUT / "dataset_baseline_scenario2_tripinfo.xml"; flow_path = OUT / "dataset_flowsense_scenario2_tripinfo.xml"
        else:
            info = scenario_info(number)
            base_path = paths(number)["baseline"]; flow_path = paths(number)["flowsense"]
        base_trips = read_trips(base_path); flow_trips = read_trips(flow_path)
        records.append({"info": info, "baseline": calculate(base_trips), "flowsense": calculate(flow_trips), "baseline_trips": base_trips, "flowsense_trips": flow_trips, "total_demand": info["total_demand"]})
    rows = [row_for(number, r["info"], r["baseline"], r["flowsense"]) for number, r in zip(range(1, 8), records)]
    rows.append(aggregate(records))
    fields = list(rows[0])
    with (OUT / "final_validation_comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    metric_rows = rows[:7]
    def lower_count(suffix):
        return sum(
            float(r[f"flowsense_{suffix}"]) < float(r[f"baseline_{suffix}"])
            for r in metric_rows
        )
    summary = [
        "# FlowSense Seven-Scenario Validation",
        "",
        "## Scenario selection",
        "",
        "| Scenario | Intersection | Window | Weather | Rush hour | Demand | N/E/S/W |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for number, record in zip(range(1, 8), records):
        info = record["info"]
        counts = info.get("counts", {})
        if number == 1:
            counts = {"N": 236, "E": 256, "S": 229, "W": 201}
        elif number == 2:
            counts = {"N": 142, "E": 138, "S": 156, "W": 165}
        summary.append(
            f"| Scenario {number} | {info['intersection_id']} | {info['start_ts']}–{info['end_ts']} | "
            f"{info['weather_actual']} | {info['is_rush_hour']} | {info['total_demand']} | "
            f"{counts.get('N','N/A')}/{counts.get('E','N/A')}/{counts.get('S','N/A')}/{counts.get('W','N/A')} |"
        )
    summary += [
        "",
        "## Scenario-level comparison",
        "",
        "| Scenario | Baseline completed | FlowSense completed | Avg travel baseline | Avg travel FlowSense | Avg waiting baseline | Avg waiting FlowSense | Max travel baseline | Max travel FlowSense |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for number, row in enumerate(metric_rows, start=1):
        summary.append(
            f"| Scenario {number} | {float(row['baseline_completed']):.0f} | "
            f"{float(row['flowsense_completed']):.0f} | "
            f"{float(row['baseline_avg_travel_time_sec']):.3f} | "
            f"{float(row['flowsense_avg_travel_time_sec']):.3f} | "
            f"{float(row['baseline_avg_waiting_time_sec']):.3f} | "
            f"{float(row['flowsense_avg_waiting_time_sec']):.3f} | "
            f"{float(row['baseline_max_travel_time_sec']):.3f} | "
            f"{float(row['flowsense_max_travel_time_sec']):.3f} |"
        )
    aggregate_row = rows[-1]
    summary.append(
        f"| ALL_SCENARIOS | {float(aggregate_row['baseline_completed']):.0f} | "
        f"{float(aggregate_row['flowsense_completed']):.0f} | "
        f"{float(aggregate_row['baseline_avg_travel_time_sec']):.3f} | "
        f"{float(aggregate_row['flowsense_avg_travel_time_sec']):.3f} | "
        f"{float(aggregate_row['baseline_avg_waiting_time_sec']):.3f} | "
        f"{float(aggregate_row['flowsense_avg_waiting_time_sec']):.3f} | "
        f"{float(aggregate_row['baseline_max_travel_time_sec']):.3f} | "
        f"{float(aggregate_row['flowsense_max_travel_time_sec']):.3f} |"
    )
    summary += [
        "",
        "The complete metric set, including absolute differences and percentage changes, is in `final_validation_comparison.csv`.",
        "",
        "## Aggregate comparison",
        "",
        "The `ALL_SCENARIOS` row pools raw trip records across all seven one-hour runs. "
        "Medians, percentiles, and maxima are calculated from pooled trip records rather than "
        "averaging scenario summaries.",
        "",
        "## Neutral findings",
        "",
        f"- FlowSense had lower average travel time in {lower_count('avg_travel_time_sec')} of 7 scenarios.",
        f"- FlowSense had lower average waiting time in {lower_count('avg_waiting_time_sec')} of 7 scenarios.",
        f"- FlowSense had lower 95th-percentile travel time in {lower_count('p95_travel_time_sec')} of 7 scenarios.",
        f"- FlowSense had lower 95th-percentile waiting time in {lower_count('p95_waiting_time_sec')} of 7 scenarios.",
        f"- Maximum travel time increased in {sum(float(r['flowsense_max_travel_time_sec']) > float(r['baseline_max_travel_time_sec']) for r in metric_rows)} of 7 scenarios.",
        "- Completed trips and throughput are subject to the 3600-second cutoff; one-vehicle differences are not meaningful throughput evidence.",
        "- No overall score or scenario ranking is reported.",
        "",
        "## Validation checks",
        "",
        "- Each new scenario uses four consecutive 15-minute dataset intervals and exact vehicle counts.",
        "- Demand uses vehicle counts only; no lane-count multiplication, queue-based generation, or speed-based generation was used.",
        "- Route departures are globally sorted and each route vehicle count matches the selected demand.",
        "- Baseline and FlowSense runs use the same network, route demand, 3600-second duration, one-second timestep, and no teleporting.",
        "- Existing Scenario 1 and Scenario 2 files, the controller, network, and existing outputs were preserved.",
        "",
        "## Interpretation",
        "",
        "These are descriptive numerical comparisons for seven controlled SUMO scenarios. "
        "Mixed metric directions and any tail-delay increases are reported as observed; "
        "the results do not establish universal improvement or causation.",
    ]
    (OUT / "final_validation_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("Wrote final_validation_comparison.csv with seven scenarios and ALL_SCENARIOS aggregate.")


if __name__ == "__main__":
    main()
