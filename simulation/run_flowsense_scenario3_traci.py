from validation_scenario_common import scenario_info, write_routes, write_config, run_baseline, run_flowsense

if __name__ == "__main__":
    info = scenario_info(3); write_routes(3, info); write_config(3); run_baseline(3); run_flowsense(3, info)
