from validation_scenario_common import scenario_info, write_routes, write_config, run_baseline, run_flowsense

if __name__ == "__main__":
    info = scenario_info(5); write_routes(5, info); write_config(5); run_baseline(5); run_flowsense(5, info)
