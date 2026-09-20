from validation_scenario_common import scenario_info, write_routes

if __name__ == "__main__":
    info = scenario_info(4)
    write_routes(4, info)
    print(f"Scenario 4 generated vehicles: {info['total_demand']}")
