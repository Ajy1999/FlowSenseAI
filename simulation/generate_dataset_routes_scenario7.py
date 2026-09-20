from validation_scenario_common import scenario_info, write_routes

if __name__ == "__main__":
    info = scenario_info(7)
    write_routes(7, info)
    print(f"Scenario 7 generated vehicles: {info['total_demand']}")
