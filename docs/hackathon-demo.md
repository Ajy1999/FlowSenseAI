# Hackathon demo guide

## Story

FlowSense asks whether traffic signals can respond to observed traffic rather
than follow a fixed schedule, and whether a short-term demand forecast adds
useful information.

## Suggested presentation flow

1. Open [notebooks/01_eda.ipynb](../notebooks/01_eda.ipynb) and show the
   15-minute traffic patterns, queues, speeds, approaches, and fixed timing.
2. Explain the architecture:
   `Dataset → FlowSense → TraCI → SUMO → evaluation metrics`.
3. Show the frozen Reactive FlowSense controller in
   [src/flowsense/controller.py](../src/flowsense/controller.py).
4. Show the isolated prediction evaluation in
   [outputs/ml_prediction/model_metrics.csv](../outputs/ml_prediction/model_metrics.csv).
5. Compare fixed-time, reactive, and predictive pooled results using
   [outputs/validation_predictive/aggregate_comparison.csv](../outputs/validation_predictive/aggregate_comparison.csv).
6. Use [outputs/validation_predictive/final_predictive_summary.txt](../outputs/validation_predictive/final_predictive_summary.txt)
   to discuss scenario-level variation and tradeoffs.

## Key message

The reactive controller is the established adaptive-control experiment.
Predictive FlowSense is a separate prototype using the same downstream control
logic with a forecast demand input. Across predictive Scenarios 2–7, its
pooled improvement over Reactive FlowSense was modest, and Scenario 2 moved in
the opposite direction for average travel and waiting time.

## Claims to avoid

- Do not call the dataset live Munich traffic.
- Do not claim universal prediction improvement.
- Do not claim prediction is the main source of the reactive controller's
  observed differences.
- Do not treat completed-trip counts from a 3600-second cutoff as proof of
  throughput improvement.
- Do not describe the prototype as production-ready infrastructure.
