from validation_scenario_common import scenario_info, write_routes, write_config, run_baseline, run_flowsense

if __name__ == "__main__":
    info = scenario_info(6); write_routes(6, info); write_config(6); run_baseline(6); run_flowsense(6, info)
