import argparse
import json

from .simulate import kpi_summary, run_comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="FlowSense adaptive traffic simulation")
    parser.add_argument("--json", action="store_true", help="print KPIs as JSON")
    args = parser.parse_args()
    summary = kpi_summary(run_comparison())
    if args.json:
        print(json.dumps(summary, indent=2))
        return
    print("FlowSense vs fixed-time baseline")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
