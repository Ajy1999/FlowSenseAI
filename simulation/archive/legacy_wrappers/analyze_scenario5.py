from validation_scenario_common import calculate, paths, read_trips

if __name__ == "__main__":
    p = paths(5); print({"baseline": calculate(read_trips(p["baseline"])), "flowsense": calculate(read_trips(p["flowsense"]))})
