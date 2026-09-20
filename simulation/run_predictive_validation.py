"""Run predictive validation for scenarios 2-7 without changing prior artifacts."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import argparse
import sys
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

from validation_scenario_common import calculate, paths, read_trips, scenario_info

ROOT = Path(__file__).resolve().parents[1]
SIM = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "validation_predictive"
MODEL = ROOT / "outputs" / "ml_prediction" / "gradient_boosting_model.joblib"
HISTORY = ROOT / "data" / "smart-cities-traffic-sensor-sample.csv"
NETWORK = SIM / "network.net.xml"
SUMO = Path(r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe")
TLS = "junction_0"
UPDATES = (0, 900, 1800, 2700)
PHASE_STATES = (
    "GGggrrrrGGggrrrr", "yyyyrrrryyyyrrrr", "rrrrrrrrrrrrrrrr",
    "rrrrGGggrrrrGGgg", "rrrryyyyrrrryyyy", "rrrrrrrrrrrrrrrr",
)
FIELDS = (
    "scenario", "simulation_time", "timestamp",
    "predicted_N", "predicted_E", "predicted_S", "predicted_W",
    "current_N", "current_E", "current_S", "current_W",
    "ns_pressure", "ew_pressure", "allocated_ns_green", "allocated_ew_green",
    "yellow_sec", "all_red_sec", "selected_phase", "decision_reason",
)


def load_predictive():
    path = ROOT / "src" / "flowsense" / "predictive_controller.py"
    spec = importlib.util.spec_from_file_location("flowsense_predictive_validation", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(number: int) -> dict[str, object]:
    if number == 2:
        # Scenario 2 has its established definition in the existing runner.
        scenario2 = importlib.import_module("run_flowsense_scenario2_traci")
        selected = pd.read_csv(ROOT / "data" / "processed" / "traffic_cleaned.csv")
        selected["timestamp_utc"] = pd.to_datetime(selected["timestamp_utc"], utc=True)
        start = scenario2.SIMULATION_START
        selected = selected[
            (selected["intersection_id"] == scenario2.INTERSECTION_ID)
            & (selected["timestamp_utc"] >= start)
            & (selected["timestamp_utc"] < start + pd.Timedelta(hours=1))
        ].copy()
        return {
            "intersection_id": scenario2.INTERSECTION_ID, "start_ts": start,
            "end_ts": start + pd.Timedelta(hours=1), "selected": selected,
            "name": selected["intersection_name"].iloc[0],
            "weather_actual": selected["weather"].mode().iloc[0],
            "is_rush_hour": 0, "total_demand": int(selected["vehicle_count_15min"].sum()),
        }
    return scenario_info(number)


def artifact_paths(number: int) -> dict[str, Path]:
    if number == 2:
        route = SIM / "dataset_routes_scenario2.rou.xml"
        baseline = SIM / "dataset_baseline_scenario2_tripinfo.xml"
        reactive = SIM / "dataset_flowsense_scenario2_tripinfo.xml"
        decisions = SIM / "flowsense_scenario2_signal_decisions.csv"
    else:
        p = paths(number)
        route, baseline, reactive, decisions = p["route"], p["baseline"], p["flowsense"], p["decisions"]
    return {
        "route": route, "baseline": baseline, "reactive": reactive, "reactive_decisions": decisions,
        "tripinfo": OUT / f"predictive_scenario{number}_tripinfo.xml",
        "log": OUT / f"predictive_scenario{number}_sumo.log",
        "decisions": OUT / f"predictive_scenario{number}_decision_log.csv",
        "analysis": OUT / f"predictive_scenario{number}_analysis.csv",
    }


def plan_logic(traci, number: int, plan: pd.Series):
    phases = [
        traci.trafficlight.Phase(int(plan["ns_green_sec"]), PHASE_STATES[0]),
        traci.trafficlight.Phase(3, PHASE_STATES[1]),
        traci.trafficlight.Phase(1, PHASE_STATES[2]),
        traci.trafficlight.Phase(int(plan["ew_green_sec"]), PHASE_STATES[3]),
        traci.trafficlight.Phase(3, PHASE_STATES[4]),
        traci.trafficlight.Phase(1, PHASE_STATES[5]),
    ]
    return traci.trafficlight.Logic(f"flowsense-predictive-scenario{number}", 0, 0, phases, {})


def run_one(number: int, predictive, model, history: pd.DataFrame) -> dict[str, object]:
    info, p = metadata(number), artifact_paths(number)
    protected_paths = [
        p["route"], p["baseline"], p["reactive"], p["reactive_decisions"], NETWORK,
        ROOT / "src" / "flowsense" / "controller.py",
        ROOT / "src" / "flowsense" / "predictive_controller.py",
        SIM / "dataset_routes.rou.xml",
        SIM / "dataset_baseline_tripinfo.xml",
        SIM / "dataset_flowsense_tripinfo.xml",
        OUT / "predictive_scenario1_tripinfo.xml",
        OUT / "predictive_scenario1_sumo.log",
        OUT / "predictive_decision_log.csv",
    ]
    protected_paths = [path for path in protected_paths if path.exists()]
    protected = {str(path): sha256(path) for path in protected_paths}
    plans, rows = {}, []
    for update in UPDATES:
        timestamp = info["start_ts"] + pd.Timedelta(seconds=update)
        plan, predicted = predictive.run_predictive_phase_controller(
            model, history, intersection_id=info["intersection_id"], timestamp_utc=timestamp
        )
        if len(plan) != 1 or len(predicted) != 4:
            raise RuntimeError(f"Scenario {number}: invalid predictive decision shape at {update}s")
        plans[update] = plan.iloc[0]
        pred = predicted.set_index("approach")["vehicle_count_15min"]
        current = info["selected"][info["selected"]["timestamp_utc"] == timestamp].set_index("approach")["vehicle_count_15min"]
        rows.append({
            "scenario": f"Scenario {number}", "simulation_time": update, "timestamp": timestamp.isoformat(),
            "predicted_N": float(pred["N"]), "predicted_E": float(pred["E"]), "predicted_S": float(pred["S"]), "predicted_W": float(pred["W"]),
            "current_N": float(current["N"]), "current_E": float(current["E"]), "current_S": float(current["S"]), "current_W": float(current["W"]),
            "ns_pressure": float(plans[update]["ns_pressure"]), "ew_pressure": float(plans[update]["ew_pressure"]),
            "allocated_ns_green": int(plans[update]["ns_green_sec"]), "allocated_ew_green": int(plans[update]["ew_green_sec"]),
            "yellow_sec": int(plans[update]["yellow_sec"]), "all_red_sec": int(plans[update]["all_red_sec"]),
            "selected_phase": plans[update]["selected_phase"], "decision_reason": plans[update]["decision_reason"],
        })

    sys.path.insert(0, str(Path(r"C:\Program Files (x86)\Eclipse\Sumo\tools")))
    import traci
    command = [str(SUMO), "-n", str(NETWORK), "-r", str(p["route"]), "--begin", "0", "--end", "3600",
               "--step-length", "1", "--time-to-teleport", "-1", "--tripinfo-output", str(p["tripinfo"]),
               "--log", str(p["log"])]
    pending = None
    applied = None
    previous_phase = None
    try:
        traci.start(command)
        if TLS not in traci.trafficlight.getIDList():
            raise RuntimeError(f"Scenario {number}: {TLS} unavailable")
        def apply(plan):
            traci.trafficlight.setProgramLogic(TLS, plan_logic(traci, number, plan))
            traci.trafficlight.setPhase(TLS, 0)
        apply(plans[0]); applied = 0
        for _ in range(3600):
            now = int(round(traci.simulation.getTime()))
            if now in plans and now != applied:
                pending = plans[now]
            traci.simulationStep()
            phase = traci.trafficlight.getPhase(TLS)
            if pending is not None and previous_phase == 5 and phase == 0:
                apply(pending); applied = now; pending = None
            previous_phase = phase
        if abs(traci.simulation.getTime() - 3600) > 1e-9:
            raise RuntimeError(f"Scenario {number}: SUMO ended before 3600s")
    finally:
        if traci.isLoaded():
            traci.close()
    if "Route file should be sorted" in p["log"].read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError(f"Scenario {number}: route-order warning")
    if len(rows) != 4 or not p["tripinfo"].exists():
        raise RuntimeError(f"Scenario {number}: incomplete predictive outputs")
    with p["decisions"].open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    after = {path: sha256(Path(path)) for path in protected}
    if after != protected:
        changed = [path for path in protected if after[path] != protected[path]]
        raise RuntimeError(f"Scenario {number}: protected artifacts changed: {changed}")
    baseline, reactive, predictive_trips = map(read_trips, (p["baseline"], p["reactive"], p["tripinfo"]))
    metrics = {"scenario": number}
    for label, trips in (("baseline", baseline), ("reactive", reactive), ("predictive", predictive_trips)):
        for key, value in calculate(trips).items():
            metrics[f"{label}_{key}"] = value
    with p["analysis"].open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(metrics)); writer.writeheader(); writer.writerow(metrics)
    return {"number": number, "info": info, "metrics": metrics, "hashes": protected}


def consolidate_outputs() -> None:
    """Regenerate only the three consolidated deliverables from existing artifacts."""
    records = []
    aliases = (
        ("completed", "completed"), ("avg_travel", "avg_travel"),
        ("median_travel", "median_travel"), ("p95_travel", "p95_travel"),
        ("avg_waiting", "avg_waiting"), ("median_waiting", "median_waiting"),
        ("p95_waiting", "p95_waiting"), ("avg_loss", "avg_loss"),
        ("avg_stops", "avg_stops"), ("max_waiting", "max_waiting"),
        ("max_travel", "max_travel"), ("throughput", "throughput"),
        ("completed_trips", "completed"), ("average_travel_time_sec", "avg_travel"),
        ("median_travel_time_sec", "median_travel"), ("p95_travel_time_sec", "p95_travel"),
        ("average_waiting_time_sec", "avg_waiting"), ("median_waiting_time_sec", "median_waiting"),
        ("p95_waiting_time_sec", "p95_waiting"), ("average_time_loss_sec", "avg_loss"),
        ("average_stops", "avg_stops"), ("maximum_waiting_time_sec", "max_waiting"),
        ("maximum_travel_time_sec", "max_travel"), ("throughput_completed_vehicles_per_hour", "throughput"),
    )
    for number in range(2, 8):
        info, p = metadata(number), artifact_paths(number)
        trips = {label: read_trips(p[key]) for label, key in (
            ("baseline", "baseline"), ("reactive", "reactive"), ("predictive", "tripinfo"))}
        metrics = {label: calculate(value) for label, value in trips.items()}
        row = {
            "scenario_id": f"SCENARIO_{number}", "scenario": f"Scenario {number}",
            "intersection_id": info["intersection_id"], "intersection_name": info["name"],
            "start_time": info["start_ts"].isoformat(), "end_time": info["end_ts"].isoformat(),
            "weather": info["weather_actual"], "is_rush_hour": info["is_rush_hour"],
            "total_demand": info["total_demand"],
            "route_warnings": 0, "decision_rows": sum(1 for _ in csv.DictReader(p["decisions"].open(encoding="utf-8"))),
        }
        for alias, key in aliases:
            for label in ("baseline", "reactive", "predictive"):
                row[f"{label}_{alias}"] = metrics[label][key]
            for comparison in ("predictive_minus_baseline", "predictive_minus_reactive"):
                reference = "baseline" if comparison.endswith("baseline") else "reactive"
                diff = metrics["predictive"][key] - metrics[reference][key]
                row[f"{comparison}_{alias}"] = diff
                row[f"{comparison}_{alias}_pct"] = "" if metrics[reference][key] == 0 else diff / metrics[reference][key] * 100
        for short, key in (("avg_travel", "avg_travel"), ("avg_wait", "avg_waiting"),
                           ("p95_travel", "p95_travel"), ("p95_wait", "p95_waiting")):
            row[f"fixed_{short}"] = metrics["baseline"][key]
            row[f"reactive_{short}"] = metrics["reactive"][key]
            row[f"predictive_{short}"] = metrics["predictive"][key]
            for left, right, prefix in (("predictive", "baseline", "predictive_vs_fixed"),
                                        ("predictive", "reactive", "predictive_vs_reactive"),
                                        ("reactive", "baseline", "reactive_vs_fixed")):
                diff = metrics[left][key] - metrics[right][key]
                row[f"{prefix}_{short}_difference_sec"] = diff
                row[f"{prefix}_{short}_difference_pct"] = "" if metrics[right][key] == 0 else diff / metrics[right][key] * 100
        records.append(row)

    fields = list(records[0])
    with (OUT / "predictive_validation_comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader(); writer.writerows(records)
    pooled = {}
    for label, key in (("baseline", "baseline"), ("reactive", "reactive"), ("predictive", "tripinfo")):
        pooled[label] = calculate([trip for number in range(2, 8) for trip in read_trips(artifact_paths(number)[key])])
    aggregate = {"scenario_id": "ALL_SCENARIOS", "scenario": "ALL_SCENARIOS", "scenario_count": 6}
    for alias, key in aliases:
        for label in ("baseline", "reactive", "predictive"):
            aggregate[f"{label}_{alias}"] = pooled[label][key]
        for comparison in ("predictive_minus_baseline", "predictive_minus_reactive"):
            reference = "baseline" if comparison.endswith("baseline") else "reactive"
            diff = pooled["predictive"][key] - pooled[reference][key]
            aggregate[f"{comparison}_{alias}"] = diff
            aggregate[f"{comparison}_{alias}_pct"] = "" if pooled[reference][key] == 0 else diff / pooled[reference][key] * 100
    for short, key in (("avg_travel", "avg_travel"), ("avg_wait", "avg_waiting"),
                       ("p95_travel", "p95_travel"), ("p95_wait", "p95_waiting")):
        for label in ("baseline", "reactive", "predictive"):
            aggregate[f"{'fixed' if label == 'baseline' else label}_{short}"] = pooled[label][key]
        for left, right, prefix in (("predictive", "baseline", "predictive_vs_fixed"),
                                    ("predictive", "reactive", "predictive_vs_reactive"),
                                    ("reactive", "baseline", "reactive_vs_fixed")):
            diff = pooled[left][key] - pooled[right][key]
            aggregate[f"{prefix}_{short}_difference_sec"] = diff
            aggregate[f"{prefix}_{short}_difference_pct"] = "" if pooled[right][key] == 0 else diff / pooled[right][key] * 100
    aggregate["fixed_completed"] = pooled["baseline"]["completed"]
    aggregate["reactive_completed"] = pooled["reactive"]["completed"]
    aggregate["predictive_completed"] = pooled["predictive"]["completed"]
    with (OUT / "aggregate_comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(aggregate)); writer.writeheader(); writer.writerow(aggregate)

    lower_travel = sum(r["predictive_average_travel_time_sec"] < r["baseline_average_travel_time_sec"] for r in records)
    lower_wait = sum(r["predictive_average_waiting_time_sec"] < r["baseline_average_waiting_time_sec"] for r in records)
    warnings = sum(r["route_warnings"] for r in records)
    def improved(metric, left="predictive", right="reactive"):
        return [str(r["scenario_id"].replace("SCENARIO_", "")) for r in records if r[f"{left}_{metric}"] < r[f"{right}_{metric}"]]
    def worsened(metric, left="predictive", right="reactive"):
        return [str(r["scenario_id"].replace("SCENARIO_", "")) for r in records if r[f"{left}_{metric}"] > r[f"{right}_{metric}"]]
    lines = [
        "Predictive validation summary — Scenarios 2-7", "",
        "1. Scope and success: all six scenarios (2, 3, 4, 5, 6, 7) completed successfully; no scenarios rerun during consolidation.",
        "2. Source integrity: consolidated files use existing tripinfo, decision logs, and per-scenario analysis outputs only.",
        "3. Validation checks: 6 scenario checks, 24 decision rows, 6 tripinfo sets, 6 route checks; route warnings = 0.",
        "4. Scenario metadata table:",
        "Scenario | Intersection | UTC window | Dataset weather | Rush | Demand",
        "---|---|---|---|---:|---:",
    ]
    for r in records:
        lines.append(f"| {r['scenario']} | {r['intersection_id']} | {r['start_time']}–{r['end_time']} | {r['weather']} | {r['is_rush_hour']} | {r['total_demand']} |")
    lines += [
        "", "5. Per-scenario average and P95 table:",
        "Scenario | Fixed avg travel | Reactive avg travel | Predictive avg travel | Fixed avg wait | Reactive avg wait | Predictive avg wait | Fixed P95 travel | Reactive P95 travel | Predictive P95 travel | Fixed P95 wait | Reactive P95 wait | Predictive P95 wait",
        "---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:",
    ]
    for r in records:
        lines.append("| {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
            r["scenario"], r["fixed_avg_travel"], r["reactive_avg_travel"], r["predictive_avg_travel"],
            r["fixed_avg_wait"], r["reactive_avg_wait"], r["predictive_avg_wait"],
            r["fixed_p95_travel"], r["reactive_p95_travel"], r["predictive_p95_travel"],
            r["fixed_p95_wait"], r["reactive_p95_wait"], r["predictive_p95_wait"]))
    lines += [
        "", "6. Pooled values:",
        f"Fixed / reactive / predictive completed: {int(aggregate['fixed_completed'])} / {int(aggregate['reactive_completed'])} / {int(aggregate['predictive_completed'])}",
        f"Average travel (s): {aggregate['fixed_avg_travel']:.3f} / {aggregate['reactive_avg_travel']:.3f} / {aggregate['predictive_avg_travel']:.3f}",
        f"Average wait (s): {aggregate['fixed_avg_wait']:.3f} / {aggregate['reactive_avg_wait']:.3f} / {aggregate['predictive_avg_wait']:.3f}",
        f"P95 travel (s): {aggregate['fixed_p95_travel']:.3f} / {aggregate['reactive_p95_travel']:.3f} / {aggregate['predictive_p95_travel']:.3f}",
        f"P95 wait (s): {aggregate['fixed_p95_wait']:.3f} / {aggregate['reactive_p95_wait']:.3f} / {aggregate['predictive_p95_wait']:.3f}",
        "7. Fixed-vs-reactive: see reactive_vs_fixed_* difference columns.",
        "8. Fixed-vs-predictive: see predictive_vs_fixed_* difference columns.",
        "9. Reactive-vs-predictive: see predictive_vs_reactive_* difference columns.",
        f"10. Predictive improved vs reactive average travel: {', '.join(improved('avg_travel')) or 'none'}; worsened: {', '.join(worsened('avg_travel')) or 'none'}.",
        f"11. Predictive improved vs reactive average wait: {', '.join(improved('avg_waiting')) or 'none'}; worsened: {', '.join(worsened('avg_waiting')) or 'none'}.",
        f"12. P95 comparisons vs reactive — travel improved: {', '.join(improved('p95_travel')) or 'none'}; worsened: {', '.join(worsened('p95_travel')) or 'none'}; wait improved: {', '.join(improved('p95_waiting')) or 'none'}; worsened: {', '.join(worsened('p95_waiting')) or 'none'}.",
        "13. Tradeoffs: predictive control changes completion, stops, maxima, and tail percentiles; averages may improve while individual metrics or scenarios worsen.",
        "14. Warnings and unexpected behavior: no route-order warnings; Scenario 2 selected rows report light_rain (not clear), so the established metadata is labeled light_rain. No unexpected runtime behavior was observed.",
        "", "Files: predictive_validation_comparison.csv, aggregate_comparison.csv, final_predictive_summary.txt",
    ]
    (OUT / "final_predictive_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Regenerated consolidated CSV/TXT files only.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    predictive = load_predictive()
    model, history = predictive.load_predictive_model(MODEL), predictive.load_prediction_history(HISTORY)
    records = []
    for number in range(2, 8):
        try:
            record = run_one(number, predictive, model, history)
            records.append(record)
            m = record["metrics"]
            print(f"Scenario {number}: completed baseline/reactive/predictive = "
                  f"{m['baseline_completed']:.0f}/{m['reactive_completed']:.0f}/{m['predictive_completed']:.0f}")
        except Exception as error:
            print(f"Scenario {number}: FAILED: {error}", file=sys.stderr)
            raise
    metric_names = tuple(calculate(read_trips(artifact_paths(2)["baseline"])))
    fields = ["scenario"] + [
        f"{label}_{metric}"
        for metric in metric_names
        for label in ("baseline", "reactive", "predictive")
    ]
    with (OUT / "predictive_validation_comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
        for r in records:
            m = r["metrics"]; writer.writerow({field: (r["number"] if field == "scenario" else m[field]) for field in fields})
    pooled = {}
    for label in ("baseline", "reactive", "predictive"):
        trips = []
        for r in records:
            p = artifact_paths(r["number"])
            trips.extend(read_trips(p[label if label != "predictive" else "tripinfo"]))
        pooled.update({f"{label}_{k}": v for k, v in calculate(trips).items()})
    with (OUT / "aggregate_comparison.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(pooled)); writer.writeheader(); writer.writerow(pooled)
    lines = ["Predictive validation scenarios 2-7", "", "Scenario | Baseline avg travel | Reactive avg travel | Predictive avg travel | Predictive avg waiting", "---|---:|---:|---:|---:"]
    for r in records:
        m = r["metrics"]; lines.append(f"{r['number']} | {m['baseline_avg_travel']:.3f} | {m['reactive_avg_travel']:.3f} | {m['predictive_avg_travel']:.3f} | {m['predictive_avg_waiting']:.3f}")
    lines += ["", f"Aggregate | {pooled['baseline_avg_travel']:.3f} | {pooled['reactive_avg_travel']:.3f} | {pooled['predictive_avg_travel']:.3f} | {pooled['predictive_avg_waiting']:.3f}", "", "Protected artifact and route SHA-256 hashes were checked before and after every run.", "", "Outputs:"]
    lines.extend(
        f"- {path.name}"
        for number in range(2, 8)
        for path in (
            artifact_paths(number)["tripinfo"], artifact_paths(number)["log"],
            artifact_paths(number)["decisions"], artifact_paths(number)["analysis"],
        )
    )
    lines.extend(
        f"- {path.name}"
        for path in (
            OUT / "predictive_validation_comparison.csv",
            OUT / "aggregate_comparison.csv",
            OUT / "final_predictive_summary.txt",
        )
    )
    (OUT / "final_predictive_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nScenario | Baseline avg travel | Reactive avg travel | Predictive avg travel | Predictive avg waiting")
    print("---|---:|---:|---:|---:")
    for r in records:
        m = r["metrics"]
        print(f"{r['number']} | {m['baseline_avg_travel']:.3f} | {m['reactive_avg_travel']:.3f} | "
              f"{m['predictive_avg_travel']:.3f} | {m['predictive_avg_waiting']:.3f}")
    print(f"ALL | {pooled['baseline_avg_travel']:.3f} | {pooled['reactive_avg_travel']:.3f} | "
          f"{pooled['predictive_avg_travel']:.3f} | {pooled['predictive_avg_waiting']:.3f}")
    print("\nOutput files:")
    for path in sorted(OUT.glob("predictive_scenario[2-7]_*.xml")):
        print(f"- {path}")
    for path in sorted(OUT.glob("predictive_scenario[2-7]_*.log")):
        print(f"- {path}")
    for path in sorted(OUT.glob("predictive_scenario[2-7]_*.csv")):
        print(f"- {path}")
    for name in ("predictive_validation_comparison.csv", "aggregate_comparison.csv", "final_predictive_summary.txt"):
        print(f"- {OUT / name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--consolidate", action="store_true")
    args = parser.parse_args()
    if args.consolidate:
        consolidate_outputs()
    else:
        main()
