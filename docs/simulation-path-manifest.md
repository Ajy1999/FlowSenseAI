# FlowSense Simulation Path Manifest

Status: Current path and cleanup manifest  
Checkpoint: `5634b71` (`Freeze validated FlowSense experiments before repository cleanup`)  
Scope: Current locations only; no paths below imply that a move has occurred.

## Current working-directory requirement

The current SUMO workflows require `simulation/` as the working directory:

```text
simulation/
```

The `.sumocfg` files use relative paths for the network, route files, and output files. Existing runners also construct paths relative to the current `simulation/` directory. This requirement remains unchanged by this manifest.

## Network files

| Current path | Status | Notes |
|---|---|---|
| `simulation/network.nod.xml` | Confirmed | SUMO network source node file |
| `simulation/network.edg.xml` | Confirmed | SUMO network source edge file |
| `simulation/network.net.xml` | Confirmed | Compiled SUMO runtime network |

These files remain at their current locations. No network-file move is part of this phase.

## Scenario 1/base experiment

| Current path | Status | Notes |
|---|---|---|
| `simulation/flowsense.sumocfg` | Confirmed | Base SUMO configuration |
| `simulation/flowsense_dataset_baseline.sumocfg` | Confirmed | Base dataset fixed-time configuration |
| `simulation/routes.rou.xml` | Confirmed | Base route input |
| `simulation/dataset_routes.rou.xml` | Confirmed | Base dataset-derived route input |
| `simulation/run_flowsense_traci.py` | Confirmed | Base reactive TraCI runner |
| `simulation/generate_dataset_routes.py` | Confirmed | Base dataset route generator |
| `simulation/analyze_dataset_baseline.py` | Confirmed | Base fixed-time analysis |
| `simulation/analyze_flowsense.py` | Confirmed | Base reactive analysis |
| `simulation/dataset_baseline_tripinfo.xml` | Confirmed | Base fixed-time tripinfo result |
| `simulation/dataset_flowsense_tripinfo.xml` | Confirmed | Base reactive tripinfo result |
| `simulation/dataset_baseline_metrics.csv` | Confirmed | Base derived metrics |
| `simulation/flowsense_signal_decisions.csv` | Confirmed | Base reactive decision log |

## Scenario 2

### Inputs and configuration

| Current path | Status | Notes |
|---|---|---|
| `simulation/dataset_routes_scenario2.rou.xml` | Confirmed | Scenario 2 route input |
| `simulation/flowsense_dataset_baseline_scenario2.sumocfg` | Confirmed | Scenario 2 fixed-time configuration |
| `simulation/run_flowsense_scenario2_traci.py` | Confirmed | Bespoke Scenario 2 reactive runner |
| `simulation/generate_dataset_routes_scenario2.py` | Confirmed | Scenario 2 route generator |

### Results and logs

| Current path | Status | Notes |
|---|---|---|
| `simulation/dataset_baseline_scenario2_tripinfo.xml` | Confirmed | Scenario 2 fixed-time tripinfo |
| `simulation/dataset_flowsense_scenario2_tripinfo.xml` | Confirmed | Scenario 2 reactive tripinfo |
| `simulation/flowsense_scenario2_signal_decisions.csv` | Confirmed | Scenario 2 reactive decision log |
| `simulation/archive/diagnostics/scenario2_baseline_sumo.log` | Archived | Scenario 2 historical SUMO log |

## Scenarios 3–7

### Route inputs

| Current path | Status |
|---|---|
| `simulation/dataset_routes_scenario3.rou.xml` | Confirmed |
| `simulation/dataset_routes_scenario4.rou.xml` | Confirmed |
| `simulation/dataset_routes_scenario5.rou.xml` | Confirmed |
| `simulation/dataset_routes_scenario6.rou.xml` | Confirmed |
| `simulation/dataset_routes_scenario7.rou.xml` | Confirmed |

### SUMO configurations

| Current path | Status |
|---|---|
| `simulation/flowsense_dataset_baseline_scenario3.sumocfg` | Confirmed |
| `simulation/flowsense_dataset_baseline_scenario4.sumocfg` | Confirmed |
| `simulation/flowsense_dataset_baseline_scenario5.sumocfg` | Confirmed |
| `simulation/flowsense_dataset_baseline_scenario6.sumocfg` | Confirmed |
| `simulation/flowsense_dataset_baseline_scenario7.sumocfg` | Confirmed |

### Tripinfo results

| Current path | Status |
|---|---|
| `simulation/dataset_baseline_scenario3_tripinfo.xml` | Confirmed |
| `simulation/dataset_baseline_scenario4_tripinfo.xml` | Confirmed |
| `simulation/dataset_baseline_scenario5_tripinfo.xml` | Confirmed |
| `simulation/dataset_baseline_scenario6_tripinfo.xml` | Confirmed |
| `simulation/dataset_baseline_scenario7_tripinfo.xml` | Confirmed |
| `simulation/dataset_flowsense_scenario3_tripinfo.xml` | Confirmed |
| `simulation/dataset_flowsense_scenario4_tripinfo.xml` | Confirmed |
| `simulation/dataset_flowsense_scenario5_tripinfo.xml` | Confirmed |
| `simulation/dataset_flowsense_scenario6_tripinfo.xml` | Confirmed |
| `simulation/dataset_flowsense_scenario7_tripinfo.xml` | Confirmed |

### Reactive decision logs

| Current path | Status |
|---|---|
| `simulation/flowsense_scenario3_signal_decisions.csv` | Confirmed |
| `simulation/flowsense_scenario4_signal_decisions.csv` | Confirmed |
| `simulation/flowsense_scenario5_signal_decisions.csv` | Confirmed |
| `simulation/flowsense_scenario6_signal_decisions.csv` | Confirmed |
| `simulation/flowsense_scenario7_signal_decisions.csv` | Confirmed |

## Final reactive results

| Current path | Status | Notes |
|---|---|---|
| `simulation/final_validation_comparison.csv` | Confirmed | Frozen seven-scenario comparison |
| `simulation/final_validation_summary.md` | Confirmed | Frozen reactive validation summary |

## Predictive outputs

All current predictive outputs are under:

```text
outputs/validation_predictive/
```

| Current path | Status | Notes |
|---|---|---|
| `outputs/validation_predictive/predictive_scenario1_tripinfo.xml` | Confirmed | Predictive Scenario 1 tripinfo |
| `outputs/validation_predictive/predictive_scenario1_sumo.log` | Confirmed | Predictive Scenario 1 SUMO log |
| `outputs/validation_predictive/predictive_decision_log.csv` | Confirmed | Predictive Scenario 1 decision log |
| `outputs/validation_predictive/predictive_scenario2_tripinfo.xml` | Confirmed | Predictive Scenario 2 tripinfo |
| `outputs/validation_predictive/predictive_scenario2_sumo.log` | Confirmed | Predictive Scenario 2 SUMO log |
| `outputs/validation_predictive/predictive_scenario2_decision_log.csv` | Confirmed | Predictive Scenario 2 decision log |
| `outputs/validation_predictive/predictive_scenario2_analysis.csv` | Confirmed | Predictive Scenario 2 analysis |
| `outputs/validation_predictive/predictive_scenario3_tripinfo.xml` | Confirmed | Predictive Scenario 3 tripinfo |
| `outputs/validation_predictive/predictive_scenario3_sumo.log` | Confirmed | Predictive Scenario 3 SUMO log |
| `outputs/validation_predictive/predictive_scenario3_decision_log.csv` | Confirmed | Predictive Scenario 3 decision log |
| `outputs/validation_predictive/predictive_scenario3_analysis.csv` | Confirmed | Predictive Scenario 3 analysis |
| `outputs/validation_predictive/predictive_scenario4_tripinfo.xml` | Confirmed | Predictive Scenario 4 tripinfo |
| `outputs/validation_predictive/predictive_scenario4_sumo.log` | Confirmed | Predictive Scenario 4 SUMO log |
| `outputs/validation_predictive/predictive_scenario4_decision_log.csv` | Confirmed | Predictive Scenario 4 decision log |
| `outputs/validation_predictive/predictive_scenario4_analysis.csv` | Confirmed | Predictive Scenario 4 analysis |
| `outputs/validation_predictive/predictive_scenario5_tripinfo.xml` | Confirmed | Predictive Scenario 5 tripinfo |
| `outputs/validation_predictive/predictive_scenario5_sumo.log` | Confirmed | Predictive Scenario 5 SUMO log |
| `outputs/validation_predictive/predictive_scenario5_decision_log.csv` | Confirmed | Predictive Scenario 5 decision log |
| `outputs/validation_predictive/predictive_scenario5_analysis.csv` | Confirmed | Predictive Scenario 5 analysis |
| `outputs/validation_predictive/predictive_scenario6_tripinfo.xml` | Confirmed | Predictive Scenario 6 tripinfo |
| `outputs/validation_predictive/predictive_scenario6_sumo.log` | Confirmed | Predictive Scenario 6 SUMO log |
| `outputs/validation_predictive/predictive_scenario6_decision_log.csv` | Confirmed | Predictive Scenario 6 decision log |
| `outputs/validation_predictive/predictive_scenario6_analysis.csv` | Confirmed | Predictive Scenario 6 analysis |
| `outputs/validation_predictive/predictive_scenario7_tripinfo.xml` | Confirmed | Predictive Scenario 7 tripinfo |
| `outputs/validation_predictive/predictive_scenario7_sumo.log` | Confirmed | Predictive Scenario 7 SUMO log |
| `outputs/validation_predictive/predictive_scenario7_decision_log.csv` | Confirmed | Predictive Scenario 7 decision log |
| `outputs/validation_predictive/predictive_scenario7_analysis.csv` | Confirmed | Predictive Scenario 7 analysis |
| `outputs/validation_predictive/predictive_validation_comparison.csv` | Confirmed | Predictive scenario comparison |
| `outputs/validation_predictive/aggregate_comparison.csv` | Confirmed | Pooled comparison |
| `outputs/validation_predictive/final_predictive_summary.txt` | Confirmed | Predictive validation summary |

## Active Python runners

| Current path | Status | Notes |
|---|---|---|
| `simulation/run_all_validation_scenarios.py` | Confirmed | Reactive Scenarios 3–7 orchestration |
| `simulation/run_flowsense_traci.py` | Confirmed | Base reactive runner |
| `simulation/run_flowsense_scenario2_traci.py` | Confirmed | Scenario 2 reactive runner |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario3_traci.py` | Archived | Scenario 3 wrapper |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario4_traci.py` | Archived | Scenario 4 wrapper |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario5_traci.py` | Archived | Scenario 5 wrapper |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario6_traci.py` | Archived | Scenario 6 wrapper |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario7_traci.py` | Archived | Scenario 7 wrapper |
| `simulation/run_predictive_scenario1.py` | Confirmed | Predictive Scenario 1 runner |
| `simulation/run_predictive_validation.py` | Confirmed | Predictive Scenarios 2–7 runner |
| `simulation/test_predictive_controller.py` | Confirmed | Predictive controller integration test |

## Analysis scripts

| Current path | Status | Notes |
|---|---|---|
| `simulation/analyze_all_validation_scenarios.py` | Confirmed | Consolidated reactive analysis |
| `simulation/analyze_dataset_baseline.py` | Confirmed | Base baseline analysis |
| `simulation/analyze_flowsense.py` | Confirmed | Base reactive analysis |
| `simulation/analyze_predictive_scenario1.py` | Confirmed | Predictive Scenario 1 analysis |
| `simulation/analyze_scenario2.py` | Confirmed | Scenario 2 analysis |
| `simulation/archive/legacy_wrappers/analyze_scenario3.py` | Archived | Scenario 3 wrapper |
| `simulation/archive/legacy_wrappers/analyze_scenario4.py` | Archived | Scenario 4 wrapper |
| `simulation/archive/legacy_wrappers/analyze_scenario5.py` | Archived | Scenario 5 wrapper |
| `simulation/archive/legacy_wrappers/analyze_scenario6.py` | Archived | Scenario 6 wrapper |
| `simulation/archive/legacy_wrappers/analyze_scenario7.py` | Archived | Scenario 7 wrapper |

## Route-generation scripts

| Current path | Status | Notes |
|---|---|---|
| `simulation/generate_dataset_routes.py` | Confirmed | Base route generator |
| `simulation/generate_dataset_routes_scenario2.py` | Confirmed | Scenario 2 route generator |
| `simulation/generate_dataset_routes_scenario3.py` | Confirmed | Scenario 3 wrapper |
| `simulation/generate_dataset_routes_scenario4.py` | Confirmed | Scenario 4 wrapper |
| `simulation/generate_dataset_routes_scenario5.py` | Confirmed | Scenario 5 wrapper |
| `simulation/generate_dataset_routes_scenario6.py` | Confirmed | Scenario 6 wrapper |
| `simulation/generate_dataset_routes_scenario7.py` | Confirmed | Scenario 7 wrapper |

## Shared scenario infrastructure

| Current path | Status | Notes |
|---|---|---|
| `simulation/validation_scenario_common.py` | Confirmed | Shared Scenario 3–7 metadata, route/config generation, execution, and metrics |

## Diagnostic files

| Current path | Status | Notes |
|---|---|---|
| `simulation/archive/diagnostics/diagnose_flowsense_scenario2.py` | Archived | Scenario 2 diagnostic analysis |
| `simulation/archive/diagnostics/diagnose_scenario2_vehicle_signal_timeline.py` | Archived | Scenario 2 per-second vehicle/signal diagnostic |
| `simulation/archive/diagnostics/scenario2_signal_timeline_800_1000.csv` | Archived | Scenario 2 diagnostic signal timeline |
| `simulation/archive/diagnostics/scenario2_vehicle_0027_timeline.csv` | Archived | Scenario 2 diagnostic vehicle timeline |
| `simulation/archive/diagnostics/scenario2_vehicle_0027_events.csv` | Archived | Scenario 2 diagnostic events |
| `simulation/archive/diagnostics/scenario2_baseline_sumo.log` | Archived | Scenario 2 historical SUMO log |

## Target directories created in Phase 2

The following directories were created during the planned cleanup. The network, scenarios, configs, routes, runners, analysis, and results directories remain empty because the validated workflows depend on the current `simulation/` layout:

```text
simulation/network/
simulation/scenarios/
simulation/configs/
simulation/routes/
simulation/runners/
simulation/analysis/
simulation/results/
simulation/archive/
simulation/archive/diagnostics/
simulation/archive/base_experiment/
simulation/archive/legacy_wrappers/
```

The populated archive directories are:

```text
simulation/archive/diagnostics/
simulation/archive/legacy_wrappers/
```

## Uncertain items

No current path listed above is marked uncertain. The Scenario 2 weather discrepancy remains a documentation/history issue: the frozen reactive summary says `clear`, while the dataset-backed predictive consolidation identifies `light_rain`; no historical result was changed.
