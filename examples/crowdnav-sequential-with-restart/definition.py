import multiprocessing as mpc
from time import sleep
from app import Boot
name = "CrowdNav-Sequential"

execution_strategy = {
    "ignore_first_n_results": 0,
    "sample_size": 10,
    "type": "sequential",
    "knobs": [
        {"route_random_sigma": 0.0},
        {"route_random_sigma": 0.2},
        {"route_random_sigma": 0.6},
        {"route_random_sigma": 0.9}
    ]
}


def change_event_creator(variables, wf):
    p1 = mpc.Process(target=Boot.start, args=(wf.process_id, True, False, wf.seed, variables, wf.car_count))
    p1.daemon = True
    p1.start()
    sleep(10)

    return variables


def primary_data_reducer(state, newData, wf):
    cnt = state["count"]
    state["avg_overhead"] = (state["avg_overhead"] * cnt + newData["overhead"]) / (cnt + 1)
    state["count"] = cnt + 1
    return state


primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-trips-0",
    "serializer": "JSON",
    "data_reducer": primary_data_reducer
}

change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "kafka:9092",
    "topic": "crowd-nav-commands-0",
    "serializer": "JSON",
}


def evaluator(resultState, wf):

    wf.change_provider["instance"].applyChange({"terminate": True})

    return resultState["avg_overhead"]


def state_initializer(state, wf):
    state["count"] = 0
    state["avg_overhead"] = 0
    return state
