from validation_scenario_common import scenario_info, write_routes

if __name__ == "__main__":
    info = scenario_info(5)
    write_routes(5, info)
    print(f"Scenario 5 generated vehicles: {info['total_demand']}")
