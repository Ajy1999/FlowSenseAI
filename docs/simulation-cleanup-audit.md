# Simulation Cleanup Audit

Status: Completed cleanup audit  
Checkpoint: `5634b7165950a55a308d5f7b0671736a84b2ee65`  
Scope: Dependency and archive assessment only. No files were moved, renamed, deleted, modified, regenerated, or executed.

## 1. Protected files

These network files are protected infrastructure and must remain permanently at their current paths:

| File | Classification | Reason |
|---|---|---|
| `simulation/network.nod.xml` | B | SUMO network source node definition |
| `simulation/network.edg.xml` | B | SUMO network source edge definition |
| `simulation/network.net.xml` | B | Compiled SUMO runtime network |

The compiled network contains references to `network.nod.xml`, `network.edg.xml`, and `network.net.xml`. Active configurations and Python runners also resolve `network.net.xml` from the `simulation/` directory. These files must not be moved, renamed, regenerated, rewritten, or modified.

Other protected infrastructure includes:

- `src/flowsense/controller.py`
- `src/flowsense/predictor.py`
- `src/flowsense/predictive_controller.py`
- `outputs/ml_prediction/gradient_boosting_model.joblib`
- `data/processed/traffic_cleaned.csv`

## 2. Active/reusable files

### A — Active/reusable code

| Current path | Active/reusable? | Role | Working-directory dependency | Archive assessment |
|---|---:|---|---:|---|
| `simulation/validation_scenario_common.py` | Yes | Shared Scenario 3–7 scenario metadata, route generation, configuration generation, SUMO execution, TraCI control, trip parsing, and metrics | Yes | Do not archive |
| `simulation/run_all_validation_scenarios.py` | Yes | Consolidated reactive orchestration for Scenarios 3–7 | Yes; imports the shared module by local name | Do not archive |
| `simulation/run_predictive_validation.py` | Yes | Predictive validation for Scenarios 2–7 and consolidation | Yes; imports Scenario 2 and shared local modules and uses `SIM / "network.net.xml"` | Do not archive |
| `simulation/run_predictive_scenario1.py` | Yes | Predictive Scenario 1 runner | Yes; resolves the network and base artifacts from `simulation/` | Do not archive |
| `simulation/run_flowsense_scenario2_traci.py` | Yes | Bespoke Scenario 2 reactive runner | Yes; direct paths to network, route, tripinfo, and decision log | Do not archive |
| `simulation/run_flowsense_traci.py` | Yes for base support | Original/base reactive runner | Yes; direct paths to base network and route files | Retain until base support is explicitly retired |
| `simulation/test_predictive_controller.py` | Yes | Predictive-controller integration test | No SUMO execution required for its core purpose, but depends on project/model paths | Do not archive while predictive support is active |
| `src/flowsense/controller.py` | Yes | Frozen reactive scoring and phase-plan logic | No simulation working-directory dependency | Do not archive |
| `src/flowsense/predictor.py` | Yes | Forecast feature engineering and exact feature order | No simulation working-directory dependency | Do not archive |
| `src/flowsense/predictive_controller.py` | Yes | Predictive adapter that delegates control logic to the frozen controller | Uses project-relative paths derived from `__file__` | Do not archive |

`validation_scenario_common.py`, `run_all_validation_scenarios.py`, and `run_predictive_validation.py` are reusable implementation, not historical wrappers. They must remain active even though wrapper scripts call into them.

## 3. Validated experiment inputs/configuration

### B — Validated inputs

| Current path | Used by | Purpose | Frozen? | Working-directory dependency | Archive assessment |
|---|---|---|---:|---:|---|
| `simulation/network.nod.xml` | Network provenance/build context | Node source | Yes | Yes | Permanently retain in place |
| `simulation/network.edg.xml` | Network provenance/build context | Edge source | Yes | Yes | Permanently retain in place |
| `simulation/network.net.xml` | All fixed, reactive, diagnostic, and predictive SUMO workflows | Runtime network | Yes | Yes | Permanently retain in place |
| `simulation/routes.rou.xml` | `flowsense.sumocfg` | Original base route input | Yes | Yes | Retain with base support |
| `simulation/dataset_routes.rou.xml` | Base dataset configuration and base runner | Base dataset route input | Yes | Yes | Retain with base support |
| `simulation/dataset_routes_scenario2.rou.xml` | Scenario 2 runner and predictive validation | Scenario 2 route input and departure schedule | Yes | Yes | Do not archive while Scenario 2 support is active |
| `simulation/dataset_routes_scenario3.rou.xml` | Shared Scenario 3–7 workflow and predictive validation | Scenario 3 route input | Yes | Yes | Do not archive |
| `simulation/dataset_routes_scenario4.rou.xml` | Shared Scenario 3–7 workflow and predictive validation | Scenario 4 route input | Yes | Yes | Do not archive |
| `simulation/dataset_routes_scenario5.rou.xml` | Shared Scenario 3–7 workflow and predictive validation | Scenario 5 route input | Yes | Yes | Do not archive |
| `simulation/dataset_routes_scenario6.rou.xml` | Shared Scenario 3–7 workflow and predictive validation | Scenario 6 route input | Yes | Yes | Do not archive |
| `simulation/dataset_routes_scenario7.rou.xml` | Shared Scenario 3–7 workflow and predictive validation | Scenario 7 route input | Yes | Yes | Do not archive |
| `simulation/flowsense.sumocfg` | Base SUMO workflow | Original/base configuration | Yes | Yes | Retain with base support |
| `simulation/flowsense_dataset_baseline.sumocfg` | Base dataset baseline workflow | Base fixed-time configuration | Yes | Yes | Retain with base support |
| `simulation/flowsense_dataset_baseline_scenario2.sumocfg` | Scenario 2 baseline workflow | Scenario 2 configuration | Yes | Yes | Do not archive |
| `simulation/flowsense_dataset_baseline_scenario3.sumocfg` | Shared Scenario 3–7 workflow | Scenario 3 baseline configuration | Yes | Yes | Do not archive |
| `simulation/flowsense_dataset_baseline_scenario4.sumocfg` | Shared Scenario 3–7 workflow | Scenario 4 baseline configuration | Yes | Yes | Do not archive |
| `simulation/flowsense_dataset_baseline_scenario5.sumocfg` | Shared Scenario 3–7 workflow | Scenario 5 baseline configuration | Yes | Yes | Do not archive |
| `simulation/flowsense_dataset_baseline_scenario6.sumocfg` | Shared Scenario 3–7 workflow | Scenario 6 baseline configuration | Yes | Yes | Do not archive |
| `simulation/flowsense_dataset_baseline_scenario7.sumocfg` | Shared Scenario 3–7 workflow | Scenario 7 baseline configuration | Yes | Yes | Do not archive |

The `.sumocfg` files use relative references such as `network.net.xml` and scenario route filenames. They currently require `simulation/` as the SUMO working directory.

## 4. Frozen outputs

### C — Frozen validated outputs

| Current path/group | Produced by | Classification | Archive assessment |
|---|---|---|---|
| `simulation/dataset_baseline_tripinfo.xml` | Base fixed-time workflow | C | Preserve; base historical evidence |
| `simulation/dataset_flowsense_tripinfo.xml` | Base reactive workflow | C | Preserve; base historical evidence |
| `simulation/dataset_baseline_scenario2_tripinfo.xml` | Scenario 2 baseline | C | Preserve as validation evidence |
| `simulation/dataset_flowsense_scenario2_tripinfo.xml` | Scenario 2 reactive runner | C | Preserve as validation evidence |
| `simulation/dataset_baseline_scenario3_tripinfo.xml` through `scenario7` | Shared baseline workflow | C | Preserve as final reactive evidence |
| `simulation/dataset_flowsense_scenario3_tripinfo.xml` through `scenario7` | Shared reactive workflow | C | Preserve as final reactive evidence |
| `simulation/flowsense_signal_decisions.csv` | Base reactive workflow | C | Preserve with base evidence |
| `simulation/flowsense_scenario2_signal_decisions.csv` | Scenario 2 reactive runner | C | Preserve as validation evidence |
| `simulation/flowsense_scenario3_signal_decisions.csv` through `scenario7` | Shared reactive workflow | C | Preserve as final reactive evidence |
| `simulation/final_validation_comparison.csv` | Final reactive consolidation | C | Frozen final evidence; do not alter |
| `simulation/final_validation_summary.md` | Final reactive consolidation | C | Frozen final evidence; do not alter |
| `outputs/validation_predictive/` | Predictive Scenario 1 and Scenarios 2–7 workflows | C | Preserve all files; do not regenerate or overwrite |

Predictive outputs include tripinfo XML, SUMO logs, decision logs, per-scenario analyses, `predictive_validation_comparison.csv`, `aggregate_comparison.csv`, and `final_predictive_summary.txt`.

The predictive outputs are outside `simulation/` and should remain outside this cleanup scope.

## 5. Diagnostics

### D — Diagnostics/investigation artifacts

| Current path | Purpose | Required by final validation? | Depends on current `simulation/` layout? | Safe to archive? |
|---|---|---:|---:|---:|
| `simulation/archive/diagnostics/diagnose_flowsense_scenario2.py` | Scenario 2 trip-level diagnostic comparison | No | Reads preserved Scenario 2 artifacts by original local paths | Archived |
| `simulation/archive/diagnostics/diagnose_scenario2_vehicle_signal_timeline.py` | Per-second vehicle/signal timeline investigation | No | Reads preserved Scenario 2 artifacts by original local paths | Archived |
| `simulation/archive/diagnostics/scenario2_baseline_sumo.log` | Historical Scenario 2 baseline log | No runtime dependency | No runtime dependency | Archived |
| `simulation/archive/diagnostics/scenario2_signal_timeline_800_1000.csv` | Diagnostic signal timeline | No runtime dependency | No runtime dependency | Archived |
| `simulation/archive/diagnostics/scenario2_vehicle_0027_timeline.csv` | Diagnostic vehicle timeline | No runtime dependency | No runtime dependency | Archived |
| `simulation/archive/diagnostics/scenario2_vehicle_0027_events.csv` | Diagnostic event summary | No runtime dependency | No runtime dependency | Archived |

These files are archived under `simulation/archive/diagnostics/`. Scenario 2 support remains active because its runner, route, configuration, tripinfo, and decision log remain in `simulation/`.

## 6. Thin wrappers

### E — Thin legacy wrappers

The following wrappers contain no independent controller, route-generation, or metric methodology. Their scenario-specific behavior is the integer scenario number passed to shared functions.

#### Reactive runner wrappers

| Current path | Delegates to | Scenario-specific behavior | Validated result role | Archive recommendation |
|---|---|---|---|---|
| `simulation/archive/legacy_wrappers/run_flowsense_scenario3_traci.py` | `validation_scenario_common.py` | Calls shared functions with `3` | Historical entry point only | Archived |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario4_traci.py` | `validation_scenario_common.py` | Calls shared functions with `4` | Historical entry point only | Archived |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario5_traci.py` | `validation_scenario_common.py` | Calls shared functions with `5` | Historical entry point only | Archived |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario6_traci.py` | `validation_scenario_common.py` | Calls shared functions with `6` | Historical entry point only | Archived |
| `simulation/archive/legacy_wrappers/run_flowsense_scenario7_traci.py` | `validation_scenario_common.py` | Calls shared functions with `7` | Historical entry point only | Archived |

#### Route-generation wrappers

| Current path | Delegates to | Scenario-specific behavior | Archive recommendation |
|---|---|---|---|
| `simulation/archive/legacy_wrappers/generate_dataset_routes_scenario3.py` | `validation_scenario_common.py` | Calls `scenario_info(3)` and `write_routes(3, info)` | Archived |
| `simulation/archive/legacy_wrappers/generate_dataset_routes_scenario4.py` | `validation_scenario_common.py` | Calls `scenario_info(4)` and `write_routes(4, info)` | Archived |
| `simulation/archive/legacy_wrappers/generate_dataset_routes_scenario5.py` | `validation_scenario_common.py` | Calls `scenario_info(5)` and `write_routes(5, info)` | Archived |
| `simulation/archive/legacy_wrappers/generate_dataset_routes_scenario6.py` | `validation_scenario_common.py` | Calls `scenario_info(6)` and `write_routes(6, info)` | Archived |
| `simulation/archive/legacy_wrappers/generate_dataset_routes_scenario7.py` | `validation_scenario_common.py` | Calls `scenario_info(7)` and `write_routes(7, info)` | Archived |

#### Analysis wrappers

| Current path | Delegates to | Scenario-specific behavior | Archive recommendation |
|---|---|---|---|
| `simulation/archive/legacy_wrappers/analyze_scenario3.py` | `validation_scenario_common.py` | Calls `paths(3)` and shared trip metrics | Archived |
| `simulation/archive/legacy_wrappers/analyze_scenario4.py` | `validation_scenario_common.py` | Calls `paths(4)` and shared trip metrics | Archived |
| `simulation/archive/legacy_wrappers/analyze_scenario5.py` | `validation_scenario_common.py` | Calls `paths(5)` and shared trip metrics | Archived |
| `simulation/archive/legacy_wrappers/analyze_scenario6.py` | `validation_scenario_common.py` | Calls `paths(6)` and shared trip metrics | Archived |
| `simulation/archive/legacy_wrappers/analyze_scenario7.py` | `validation_scenario_common.py` | Calls `paths(7)` and shared trip metrics | Archived |

These wrappers are genuinely redundant for the consolidated workflow. They were archived, not deleted, after:

1. Shared route generation is verified against frozen route files.
2. Shared baseline/reactive execution is verified in temporary output locations.
3. Metrics and decision logs are compared against frozen results.
4. The existing wrappers are retained in a legacy archive.

## 7. Dependencies and path risks

### Current working-directory requirement

The current SUMO workflows require:

```text
simulation/
```

because `.sumocfg` files use relative paths and local imports assume the scripts are run from that directory.

### Direct path dependencies

The following active code directly resolves network or scenario artifacts from `simulation/`:

- `validation_scenario_common.py`
- `run_all_validation_scenarios.py`
- `run_predictive_validation.py`
- `run_flowsense_traci.py`
- `run_flowsense_scenario2_traci.py`
- `run_predictive_scenario1.py`
- `diagnose_scenario2_vehicle_signal_timeline.py`

### Local module imports

The following active scripts import `validation_scenario_common` by module name:

- `run_all_validation_scenarios.py`
- `analyze_all_validation_scenarios.py`
- `run_predictive_validation.py`

Moving these scripts without preserving module discoverability or updating imports would break them.

### In-place writes

`validation_scenario_common.py` writes route, configuration, tripinfo, and decision artifacts into the current `simulation/` directory. Rerunning it can overwrite validated files. Any future validation must use temporary output paths or a protected copy and must not overwrite frozen evidence.

### Predictive dependencies

`run_predictive_validation.py` reads existing Scenario 2–7 routes, reactive tripinfo, reactive decision logs, the protected network, the model, and the predictive controller. Moving any one of these requires coordinated path changes.

### Historical output references

Frozen tripinfo XML and SUMO log files contain historical network path references. Those references are evidence and must not be rewritten during cleanup.

### External runtime dependency

The runners use hard-coded Windows SUMO paths:

```text
C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe
C:\Program Files (x86)\Eclipse\Sumo\tools
```

This is an environment dependency, not a reason to alter the frozen experiment.

## 8. Recommended archive candidates

### Safe after validation

| Candidate group | Why safe to archive | What depends on it |
|---|---|---|
| `simulation/archive/legacy_wrappers/` Scenario 3–7 route-generation wrappers | Thin delegators; shared implementation is in `validation_scenario_common.py` | No active script requires the archived wrapper files |
| `simulation/archive/legacy_wrappers/` Scenario 3–7 reactive runner wrappers | Thin delegators; consolidated orchestration is `run_all_validation_scenarios.py` | No active script imports the archived wrappers |
| `simulation/archive/legacy_wrappers/` Scenario 3–7 analysis wrappers | Thin delegators; consolidated analysis is `analyze_all_validation_scenarios.py` | No active script imports the archived wrappers |
| `simulation/archive/diagnostics/` Scenario 2 diagnostic scripts | Investigation-only logic | They depend on preserved Scenario 2 inputs/results but are not required by final validation |
| `simulation/archive/diagnostics/` Scenario 2 diagnostic CSVs and log | Historical investigation evidence | No active runner depends on these files |
| Base analysis scripts | Base-only metrics utilities | Base tripinfo and decision files; archive only if base workflow is no longer a required demo path |
| Base route generator | Base-only route generation utility | Base dataset and configuration paths |
| Base route/config/output files | Historical/base experiment evidence | Base runners and analyses; archive only after base support is explicitly retired |

### Not safe to archive now

- Protected network files.
- `validation_scenario_common.py`.
- `run_all_validation_scenarios.py`.
- `run_predictive_validation.py`.
- `run_flowsense_scenario2_traci.py`.
- Scenario 2 route/config/result files.
- Scenario 3–7 route files and baseline/reactive outputs.
- Final reactive comparison and summary.
- Predictive validation outputs.
- Predictive controller, predictor, and model files.

## 9. Files that should remain permanently in `simulation/`

Because the network and current SUMO workflows are tightly coupled to the existing layout, the following should remain at their current paths unless a separately approved compatibility redesign is completed:

### Permanently fixed infrastructure

- `simulation/network.nod.xml`
- `simulation/network.edg.xml`
- `simulation/network.net.xml`

### Current active SUMO inputs

- `simulation/*.sumocfg`
- `simulation/dataset_routes*.rou.xml`
- `simulation/routes.rou.xml`

### Current active reusable workflow

- `simulation/validation_scenario_common.py`
- `simulation/run_all_validation_scenarios.py`
- `simulation/run_predictive_validation.py`
- `simulation/run_flowsense_scenario2_traci.py`
- `simulation/run_predictive_scenario1.py`

Scenario-specific wrappers may eventually be archived, but no active workflow currently requires moving them to do so.

## 10. Proposed future cleanup order

This is a future plan only; no step below was performed in this audit.

1. Preserve the checkpoint and record hashes for all frozen inputs and outputs.
2. Leave all three network files permanently in `simulation/`.
3. Add a path manifest or path registry without changing current runtime behavior.
4. Archive diagnostic CSVs and logs only; verify no active references.
5. Archive diagnostic scripts while preserving Scenario 2 support.
6. Validate the consolidated Scenario 3–7 runner and analysis against frozen results using temporary outputs.
7. Archive the Scenario 3–7 route, runner, and analysis wrappers after validation; retain them as legacy wrappers. Completed in `simulation/archive/legacy_wrappers/`.
8. Decide separately whether the base/Scenario 1 workflow remains a demo requirement.
9. If the base workflow is retired, archive its scripts and artifacts together, not individually.
10. Keep final reactive results and all predictive outputs frozen and outside destructive cleanup.
11. Update documentation last, including the Scenario 2 weather-label inconsistency:
    - frozen reactive summary: `clear`
    - dataset-backed predictive consolidation: `light_rain`
12. Do not delete any file until reproducibility has been demonstrated from the preserved checkpoint and the archive.

## Classification summary

| Category | Meaning | Main members |
|---|---|---|
| A | Active/reusable code | Shared validation, predictive runners, controller, predictor |
| B | Validated experiment inputs/configuration | Network, routes, SUMO configs |
| C | Frozen validated outputs | Tripinfo, decision logs, final summaries, predictive outputs |
| D | Diagnostics/investigation artifacts | Scenario 2 diagnostic scripts, logs, and CSVs |
| E | Thin legacy wrappers | Scenario 3–7 route, runner, and analysis wrappers |
| F | Safe-to-archive documentation/support files | Historical base support and investigation records after validation |

## Completed cleanup verification

- Scenario 2 diagnostic artifacts are archived under `simulation/archive/diagnostics/`.
- Fifteen redundant Scenario 3–7 wrappers are archived under `simulation/archive/legacy_wrappers/`.
- The consolidated Scenario 3–7 workflow was validated in an isolated workspace.
- Temporary route generation, SUMO execution, metrics, and decision logs reproduced the frozen Scenario 3–7 evidence exactly.
- No active references to the archived wrappers remain; documentation references are historical only.
- The network files remain in their original `simulation/` locations because of relative-path and working-directory coupling.
- The Scenario 2 weather label discrepancy remains documented: the frozen reactive summary says `clear`, while the dataset-backed predictive consolidation identifies `light_rain`. Historical evidence was not changed.

## Final repository structure

```text
simulation/
  active experiment and reusable validation workflow
  protected network files
  validated scenario inputs and results

simulation/archive/
  diagnostics/
    historical Scenario 2 diagnostic artifacts
  legacy_wrappers/
    redundant Scenario 3–7 wrapper scripts

src/flowsense/
  active controller and prediction code

outputs/
  ML and predictive validation outputs

docs/
  cleanup and path documentation
```
