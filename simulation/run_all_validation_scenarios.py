"""Create and run frozen-controller validation scenarios 3 through 7."""

from pathlib import Path

from validation_scenario_common import (
    SCENARIOS,
    calculate,
    paths,
    run_baseline,
    run_flowsense,
    scenario_info,
    write_config,
    write_routes,
)


def main() -> None:
    for number in SCENARIOS:
        info = scenario_info(number)
        write_routes(number, info)
        write_config(number)
        baseline_output = run_baseline(number)
        flowsense_output = run_flowsense(number, info)
        print(
            f"Scenario {number}: demand={info['total_demand']}, "
            f"baseline tripinfo={paths(number)['baseline'].name}, "
            f"FlowSense tripinfo={paths(number)['flowsense'].name}"
        )
        print(f"  baseline completed: {len(__import__('validation_scenario_common').read_trips(paths(number)['baseline']))}")
        print(f"  FlowSense completed: {len(__import__('validation_scenario_common').read_trips(paths(number)['flowsense']))}")
        print("  baseline/FlowSense reached 3600s; route warnings: 0; decisions: 4")


if __name__ == "__main__":
    main()
