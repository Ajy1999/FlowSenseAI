# Validation results

## Reactive seven-scenario validation

The frozen reactive validation covers seven controlled one-hour SUMO scenarios.
The complete comparison is in
[simulation/final_validation_comparison.csv](../simulation/final_validation_comparison.csv),
with the narrative in
[simulation/final_validation_summary.md](../simulation/final_validation_summary.md).

The scenarios use exact dataset-derived 15-minute vehicle counts and a
fixed 3600-second simulation cutoff. Completed trips are therefore not
reported as independent throughput evidence.

## Predictive Scenarios 2–7

The predictive controller uses the same control logic as Reactive FlowSense and
changes only the demand input from current count to predicted next-interval
count.

| Metric | Fixed-time | Reactive | Predictive |
|---|---:|---:|---:|
| Average travel time (s) | 54.989 | 52.857 | 52.751 |
| Average waiting time (s) | 11.368 | 9.263 | 9.178 |
| P95 travel time (s) | 85 | 79 | 78 |
| P95 waiting time (s) | 40 | 34 | 32 |

These are pooled raw-trip metrics across Scenarios 2–7. Predictive FlowSense's
additional reduction relative to Reactive FlowSense is modest:

- average travel time: 0.106 seconds lower;
- average waiting time: 0.086 seconds lower;
- P95 travel time: 1 second lower;
- P95 waiting time: 2 seconds lower.

The scenario-level result is mixed: Predictive FlowSense had higher average
travel and waiting values than Reactive FlowSense in Scenario 2, and lower
values in Scenarios 3–7.

## Metadata note

The frozen reactive summary labels Scenario 2 weather as `clear`, while the
predictive consolidation identifies the selected dataset rows as `light_rain`.
Both result files are preserved. This documentation reports the discrepancy
instead of changing either historical result.

## Scope

These results are descriptive controlled SUMO experiments using a synthetic,
anonymized dataset. They do not establish universal improvement, causation, or
production readiness.
