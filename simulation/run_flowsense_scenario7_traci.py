from validation_scenario_common import scenario_info, write_routes, write_config, run_baseline, run_flowsense

if __name__ == "__main__":
    info = scenario_info(7); write_routes(7, info); write_config(7); run_baseline(7); run_flowsense(7, info)
