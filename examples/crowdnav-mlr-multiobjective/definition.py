import multiprocessing as mpc
from time import sleep

# first run 'Rscript start_R_server.R' in https://github.com/alinaciuysal/mlrMBO-API
name = "MLR-MBO bayesian optimization - multiobjective"
id = 1

execution_strategy = {
    "ignore_first_n_results": 0,
    "sample_size": 10,
    "type": "mlr_mbo",
    "optimizer_iterations": 2,
    "optimizer_iterations_in_design": 3,
    "population_size": 3,
    "objectives_number": 2,
    "knobs": {
        "route_random_sigma": (0.0, 1.0)
    }
}


def primary_data_reducer(state, new_data, wf):
    cnt = state["count_overhead"]
    state["avg_overhead"] = (state["avg_overhead"] * cnt + new_data["overhead"]) / (cnt + 1)
    state["count_overhead"] = cnt + 1
    return state


def performance_data_reducer(state, new_data, wf):
    cnt = state["count_performance"]
    state["avg_performance"] = (state["avg_performance"] * cnt + new_data["duration"]) / (cnt + 1)
    state["count_performance"] = cnt + 1
    return state


primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-trips-0",
    "serializer": "JSON",
    "data_reducer": primary_data_reducer
}

secondary_data_providers = [
    {
        "type": "kafka_consumer",
        "kafka_uri": "kafka:9092",
        "topic": "crowd-nav-routing-0",
        "serializer": "JSON",
        "data_reducer": performance_data_reducer
    }
]
change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-commands-0",
    "serializer": "JSON",
}


def change_event_creator(variables, wf):
    from app import Boot
    p1 = mpc.Process(target=Boot.start, args=(wf.processor_id, True, False, wf.seed, variables, wf.car_count))
    p1.daemon = True
    p1.start()
    sleep(10)

    return variables


def evaluator(result_state, wf):

    wf.change_provider["instance"].applyChange({"terminate": True})

    return result_state["avg_overhead"], result_state["avg_performance"]


def state_initializer(state, wf):
    state["count_performance"] = 0
    state["count_overhead"] = 0
    state["avg_overhead"] = 0
    state["avg_performance"] = 0
    return state
