# Simple sequential run of knob values
name = "CrowdNav-elasticsearch with 2 outputs"


def evaluator(resultState, wf):
    return wf.experimentCounter


def state_initializer(state, wf):
    state["overhead_data_points"] = 0
    state["routing_data_points"] = 0
    return state


def primary_data_reducer(state, newData, wf):
    wf.db.save_data_point(wf.experimentCounter, wf.current_knobs, newData, state["overhead_data_points"], wf.rtx_run_id, "overhead")
    state["overhead_data_points"] += 1
    return state


def routing_data_reducer(state, newData, wf):
    wf.db.save_data_point(wf.experimentCounter, wf.current_knobs, newData, state["routing_data_points"], wf.rtx_run_id, "routing")
    state["routing_data_points"] += 1
    return state


execution_strategy = {
    "ignore_first_n_results": 10,
    "sample_size": 10,
    "type": "sequential",
    "knobs": [
        {"route_random_sigma": 0.0},
        {"route_random_sigma": 0.2}
    ]
}

primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-trips-0",
    "serializer": "JSON",
    "data_reducer": primary_data_reducer
}

secondary_data_providers = [
    {
        "type": "kafka_consumer",
        "kafka_uri": "localhost:9092",
        "topic": "crowd-nav-routing-0",
        "serializer": "JSON",
        "data_reducer": routing_data_reducer
    }
]

change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-commands-0",
    "serializer": "JSON",
}