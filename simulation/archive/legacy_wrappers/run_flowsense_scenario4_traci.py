from validation_scenario_common import scenario_info, write_routes, write_config, run_baseline, run_flowsense

if __name__ == "__main__":
    info = scenario_info(4); write_routes(4, info); write_config(4); run_baseline(4); run_flowsense(4, info)
