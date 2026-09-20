from validation_scenario_common import scenario_info, write_routes

if __name__ == "__main__":
    info = scenario_info(3)
    write_routes(3, info)
    print(f"Scenario 3 generated vehicles: {info['total_demand']}")
