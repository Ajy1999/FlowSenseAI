# Experiment guide

## Reproducibility

The completed experiments are frozen. Do not regenerate or overwrite existing
results unless a new experiment is explicitly intended.

The primary analysis notebook is
[notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb).

The ML training entry point is
[ml/train_traffic_predictor.py](../ml/train_traffic_predictor.py). Its saved
model and evaluation artifacts are in
[outputs/ml_prediction/](../outputs/ml_prediction/).

SUMO requires the installed Eclipse SUMO tools and executable. The existing
simulation scripts use the repository's current Windows-specific SUMO paths
and direct file layout; preserve those paths when reproducing historical
results.

## Validation variants

The repository contains:

1. Fixed-time baseline runs.
2. Reactive FlowSense runs.
3. Predictive FlowSense runs.

All controlled scenarios use the same network, route demand, departure times,
vehicle types, 3600-second duration, one-second timestep, and no teleporting
where specified by the existing validation methodology.

The seven-scenario reactive results are summarized in
[simulation/final_validation_summary.md](../simulation/final_validation_summary.md).
Predictive Scenarios 2–7 are summarized in
[outputs/validation_predictive/final_predictive_summary.txt](../outputs/validation_predictive/final_predictive_summary.txt).

## Interpreting results

Tripinfo metrics describe completed vehicles within a fixed simulation cutoff.
Small differences in completed vehicles can result from that cutoff and should
not be interpreted as standalone throughput evidence.

The experiments use synthetic/anonymized demand and controlled SUMO scenarios.
They support prototype comparison, not claims about live Munich traffic or
deployment readiness.
