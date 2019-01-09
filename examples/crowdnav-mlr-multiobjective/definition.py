import multiprocessing as mpc
from time import sleep

# first run 'Rscript start_R_server.R' in https://github.com/alinaciuysal/mlrMBO-API
name = "MLR-MBO bayesian optimization - multiobjective"

execution_strategy = {
    "ignore_first_n_results": 0,
    "sample_size": 5000,
    "type": "mlr_mbo",
    "optimizer_iterations": 92,
    "optimizer_iterations_in_design": 8,
    "population_size": 1,
    "objectives_number": 2,
    "knobs": {
        "route_random_sigma": (0.0, 0.3),
        "exploration_percentage": (0.0, 0.3),
        "max_speed_and_length_factor": (1, 2.5),
        "average_edge_duration_factor": (1, 2.5),
        "freshness_update_factor": (5, 20),
        "freshness_cut_off_value": (100, 700),
        "re_route_every_ticks": (10, 70)
    },
    "knob_types": {
        "route_random_sigma": "real",
        "exploration_percentage": "real",
        "max_speed_and_length_factor": "real",
        "average_edge_duration_factor": "real",
        "freshness_update_factor": "int",
        "freshness_cut_off_value": "int",
        "re_route_every_ticks": "int"
    }
}


def primary_data_reducer(state, new_data, wf):
    state["overheads"].append(new_data["overhead"])
    cnt = state["count_overhead"]
    state["avg_overhead"] = (state["avg_overhead"] * cnt + new_data["overhead"]) / (cnt + 1)
    state["count_overhead"] = cnt + 1
    return state


def routing_performance_data_reducer(state, new_data, wf):
    state["routings"].append(new_data["duration"])
    cnt = state["count_routing"]
    state["avg_routing"] = (state["avg_routing"] * cnt + new_data["duration"]) / (cnt + 1)
    state["count_routing"] = cnt + 1
    return state


primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-trips",
    "serializer": "JSON",
    "data_reducer": primary_data_reducer
}

secondary_data_providers = [
    {
        "type": "kafka_consumer",
        "kafka_uri": "kafka:9092",
        "topic": "crowd-nav-routing",
        "serializer": "JSON",
        "data_reducer": routing_performance_data_reducer
    }
]
change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-commands",
    "serializer": "JSON",
}


def change_event_creator(variables, wf):
    from app import Boot
    p1 = mpc.Process(target=Boot.start, args=(wf.seed, True, False, wf.seed, variables, wf.car_count))
    p1.daemon = True
    p1.start()
    sleep(10)

    return variables


def evaluator(result_state, wf):

    wf.change_provider["instance"].applyChange({"terminate": True})

    data_to_save = {}
    data_to_save["overheads"] = result_state["overheads"]
    data_to_save["routings"] = result_state["routings"]
    wf.db.save_data_for_experiment(wf.experimentCounter, wf.current_knobs, data_to_save, wf.rtx_run_id, 0)

    return result_state["avg_overhead"], result_state["avg_routing"]


def state_initializer(state, wf):
    state["overheads"] = []
    state["routings"] = []
    state["count_routing"] = 0
    state["count_overhead"] = 0
    state["avg_overhead"] = 0
    state["avg_routing"] = 0
    return state
