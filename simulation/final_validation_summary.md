# FlowSense Seven-Scenario Validation

## Scenario selection

| Scenario | Intersection | Window | Weather | Rush hour | Demand | N/E/S/W |
|---|---|---|---|---:|---:|---|
| Scenario 1 | INT-EXPO-E | 2026-09-17T09:00:00+00:00–2026-09-17T10:00:00+00:00 | clear | 1 | 922 | 236/256/229/201 |
| Scenario 2 | INT-EXPO-N | 2026-09-13T10:00:00+00:00–2026-09-13T11:00:00+00:00 | clear | 0 | 601 | 142/138/156/165 |
| Scenario 3 | INT-RING-01 | 2026-09-14 08:15:00+00:00–2026-09-14 09:15:00+00:00 | clear | 1 | 920 | 187/233/258/242 |
| Scenario 4 | INT-EXPO-S | 2026-09-14 09:00:00+00:00–2026-09-14 10:00:00+00:00 | clear | 1 | 873 | 236/195/189/253 |
| Scenario 5 | INT-EXPO-E | 2026-09-17 05:30:00+00:00–2026-09-17 06:30:00+00:00 | cloudy | 0 | 756 | 186/187/187/196 |
| Scenario 6 | INT-RING-01 | 2026-09-18 07:15:00+00:00–2026-09-18 08:15:00+00:00 | light_rain | 1 | 796 | 187/216/183/210 |
| Scenario 7 | INT-EXPO-N | 2026-09-19 12:00:00+00:00–2026-09-19 13:00:00+00:00 | clear | 0 | 758 | 194/197/181/186 |

## Scenario-level comparison

| Scenario | Baseline completed | FlowSense completed | Avg travel baseline | Avg travel FlowSense | Avg waiting baseline | Avg waiting FlowSense | Max travel baseline | Max travel FlowSense |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Scenario 1 | 908 | 909 | 55.947 | 53.216 | 12.152 | 9.580 | 100.000 | 98.000 |
| Scenario 2 | 592 | 592 | 54.194 | 52.443 | 10.630 | 8.782 | 91.000 | 105.000 |
| Scenario 3 | 905 | 907 | 55.440 | 52.722 | 11.709 | 9.095 | 94.000 | 93.000 |
| Scenario 4 | 859 | 861 | 55.402 | 52.764 | 11.703 | 9.120 | 103.000 | 94.000 |
| Scenario 5 | 745 | 746 | 54.662 | 53.038 | 11.093 | 9.425 | 95.000 | 92.000 |
| Scenario 6 | 785 | 785 | 55.183 | 53.074 | 11.622 | 9.628 | 102.000 | 98.000 |
| Scenario 7 | 747 | 747 | 54.719 | 53.047 | 11.162 | 9.470 | 96.000 | 95.000 |
| ALL_SCENARIOS | 5541 | 5547 | 55.146 | 52.916 | 11.496 | 9.315 | 103.000 | 105.000 |

The complete metric set, including absolute differences and percentage changes, is in `final_validation_comparison.csv`.

## Aggregate comparison

The `ALL_SCENARIOS` row pools raw trip records across all seven one-hour runs. Medians, percentiles, and maxima are calculated from pooled trip records rather than averaging scenario summaries.

## Neutral findings

- FlowSense had lower average travel time in 7 of 7 scenarios.
- FlowSense had lower average waiting time in 7 of 7 scenarios.
- FlowSense had lower 95th-percentile travel time in 7 of 7 scenarios.
- FlowSense had lower 95th-percentile waiting time in 7 of 7 scenarios.
- Maximum travel time increased in 1 of 7 scenarios.
- Completed trips and throughput are subject to the 3600-second cutoff; one-vehicle differences are not meaningful throughput evidence.
- No overall score or scenario ranking is reported.

## Validation checks

- Each new scenario uses four consecutive 15-minute dataset intervals and exact vehicle counts.
- Demand uses vehicle counts only; no lane-count multiplication, queue-based generation, or speed-based generation was used.
- Route departures are globally sorted and each route vehicle count matches the selected demand.
- Baseline and FlowSense runs use the same network, route demand, 3600-second duration, one-second timestep, and no teleporting.
- Existing Scenario 1 and Scenario 2 files, the controller, network, and existing outputs were preserved.

## Interpretation

These are descriptive numerical comparisons for seven controlled SUMO scenarios. Mixed metric directions and any tail-delay increases are reported as observed; the results do not establish universal improvement or causation.
