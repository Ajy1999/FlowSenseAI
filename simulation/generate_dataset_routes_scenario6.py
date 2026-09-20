from validation_scenario_common import scenario_info, write_routes

if __name__ == "__main__":
    info = scenario_info(6)
    write_routes(6, info)
    print(f"Scenario 6 generated vehicles: {info['total_demand']}")
