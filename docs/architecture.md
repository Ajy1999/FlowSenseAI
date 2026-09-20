# FlowSense architecture

## Pipeline

```text
Traffic sensor dataset
        ↓
Feature preparation / EDA
        ↓
┌─────────────────────────────┐
│ Fixed-time baseline         │
│ Reactive FlowSense          │
│ Predictive FlowSense        │
└─────────────────────────────┘
        ↓
TraCI
        ↓
SUMO
        ↓
Tripinfo and comparison metrics
```

## Control modes

### Fixed-time baseline

Uses the existing fixed signal program without adaptive decisions.

### Reactive FlowSense

Uses current approach measurements:

- vehicle count
- queue length
- average speed

The frozen controller normalizes demand, queue, and speed congestion, applies
weights of 0.30, 0.40, and 0.30, and creates the existing NS/EW phase plan.

### Predictive FlowSense

Uses the trained Gradient Boosting model to predict the next 15-minute vehicle
count independently for each intersection and approach. Those predictions
replace only the current vehicle-count input. Pressure scoring, phase
selection, green-time bounds, yellow time, all-red time, and safe phase-boundary
updates remain the same as Reactive FlowSense.

The predictive simulation uses the historical dataset as the feature source.
This is a controlled simulation setup, not a live sensor deployment.

## Project modules

- `src/flowsense/controller.py`: reactive scoring and phase-plan generation.
- `src/flowsense/predictor.py`: grouped forecasting feature construction.
- `src/flowsense/predictive_controller.py`: model inference adapter.
- `ml/train_traffic_predictor.py`: isolated model training and evaluation.
- `simulation/`: frozen SUMO network, routes, runners, and validation assets.

The existing paths are retained because completed experiments reference them
directly.
