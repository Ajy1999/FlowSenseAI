# FlowSense AI: Adaptive Traffic Signal Control

**Signals that respond to traffic, not schedules.**

## Research questions

**Primary:** Can adaptive traffic signal timing based on real-time traffic
demand reduce vehicle delay and queue lengths compared with fixed-time signal
control?

**Secondary:** Does short-term traffic prediction provide additional
improvement over purely reactive control?

## Project overview

FlowSense is a staged prototype for dataset-driven adaptive traffic-signal
control:

```text
Dataset → FlowSense → TraCI → SUMO → evaluation metrics
```

The repository contains three control modes:

1. **Fixed-time baseline** — the existing fixed signal program.
2. **Reactive FlowSense** — scores current demand, queue length, and speed
   congestion, then allocates the existing NS/EW phase plan.
3. **Predictive FlowSense** — uses the same FlowSense scoring, pressure, phase,
   and green-time logic as Reactive FlowSense, but replaces current vehicle
   demand with the Gradient Boosting prediction for the next 15-minute
   interval.

Predictive FlowSense is an additive prototype. It has not replaced or modified
the reactive controller.

## Dataset

The project uses a synthetic, anonymized traffic-sensor dataset covering:

- 7 simulated days
- 15-minute observations
- 6 intersections
- 4 approaches per intersection: N, E, S, and W

Available traffic variables include timestamp, intersection identity and
location, approach, lane count, vehicle count per 15 minutes, average speed,
queue length, fixed green and red signal timing, rush-hour status, weather,
and notes.

This is **not live Munich traffic** and does not represent live city
infrastructure.

The original local dataset is
[data/smart-cities-traffic-sensor-sample.csv](data/smart-cities-traffic-sensor-sample.csv).
The processed dataset used by the EDA and SUMO demand generation is
[data/processed/traffic_cleaned.csv](data/processed/traffic_cleaned.csv).

## Machine-learning prediction layer

The isolated prediction model is a scikit-learn `GradientBoostingRegressor`.
Its target is the next 15-minute `vehicle_count_15min` within each
`(intersection_id, approach)` time series.

Features include current measurements, grouped 15/30/45-minute demand lags,
time features, rush-hour status, weather, intersection, and approach. The
split is chronological rather than randomly shuffled. The evaluation cutoff
was `2026-09-18 14:00:00 UTC`.

| Model | MAE | RMSE | R² |
|---|---:|---:|---:|
| Persistence baseline | 7.6396 | 9.3957 | -0.1501 |
| Gradient Boosting | 5.8570 | 7.0082 | 0.3601 |

Gradient Boosting reduced MAE by approximately **23.3%** relative to
persistence on the held-out test set. This is a synthetic-data holdout result,
not a production guarantee.

Artifacts are in
[outputs/ml_prediction/](outputs/ml_prediction/), including the trained model,
metrics, predictions, feature importance, and training configuration.

## Validation

Seven controlled SUMO scenarios were tested using fixed-time and Reactive
FlowSense control. The scenarios use fixed 3600-second simulation windows,
exact dataset-derived demand, the same network and routes, and straight-through
vehicle movements.

The completed reactive validation is documented in
[simulation/final_validation_summary.md](simulation/final_validation_summary.md)
and [simulation/final_validation_comparison.csv](simulation/final_validation_comparison.csv).

Completed-trip counts are affected by the fixed 3600-second cutoff. They are
reported as simulation outcomes and should **not** be treated as independent
throughput evidence or proof of throughput improvement.

## Predictive validation: Scenarios 2–7

The pooled predictive comparison uses the already generated raw trip records
for Scenarios 2–7:

| Metric | Fixed-time | Reactive | Predictive |
|---|---:|---:|---:|
| Average travel time (s) | 54.989 | 52.857 | 52.751 |
| Average waiting time (s) | 11.368 | 9.263 | 9.178 |
| P95 travel time (s) | 85 | 79 | 78 |
| P95 waiting time (s) | 40 | 34 | 32 |

Predictive FlowSense produced lower pooled values than Reactive FlowSense for
these four metrics, but the additional improvement was **modest**. At the
scenario level, average travel time and average waiting time were slightly
higher for Predictive FlowSense in Scenario 2 and lower in Scenarios 3–7.
The results therefore do not establish universal predictive superiority.

See [outputs/validation_predictive/final_predictive_summary.txt](outputs/validation_predictive/final_predictive_summary.txt)
and [outputs/validation_predictive/aggregate_comparison.csv](outputs/validation_predictive/aggregate_comparison.csv).

## Limitations

- The dataset is synthetic and anonymized.
- SUMO validation uses a single-intersection network.
- Vehicles are straight-through because turn destinations are not provided.
- The ML evaluation uses one chronological holdout.
- Feature importance is descriptive, not causal.
- Predictive FlowSense is a prototype, not deployment-ready traffic
  infrastructure.
- No real-world sensor validation has been performed.

## Future work

- Evaluate LSTM or other temporal models.
- Investigate reinforcement learning.
- Coordinate multiple intersections.
- Add richer turning movements and destination information.
- Validate against real-world sensor data.

## Repository guide

- [notebooks/01_eda.ipynb](notebooks/01_eda.ipynb) — exploratory analysis.
- [src/flowsense/controller.py](src/flowsense/controller.py) — frozen reactive
  controller and shared phase-plan logic.
- [src/flowsense/predictive_controller.py](src/flowsense/predictive_controller.py)
  — predictive demand adapter.
- [ml/train_traffic_predictor.py](ml/train_traffic_predictor.py) — ML training
  and evaluation entry point.
- [simulation/](simulation/) — SUMO network, routes, runners, diagnostics,
  and frozen reactive validation artifacts.
- [outputs/](outputs/) — ML and predictive-validation artifacts.

Existing experiment paths and result files are intentionally preserved for
reproducibility.
