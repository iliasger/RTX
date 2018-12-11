name = "CrowdNav-Bayesian-2objectives"

execution_strategy = {
    "ignore_first_n_results": 10,
    "sample_size": 10,
    "type": "self_optimizer",
    "optimizer_method": "gauss",
    "optimizer_iterations": 5,
    "optimizer_random_starts": 1,
    "knobs": {
        "route_random_sigma": (0.0, 0.3),
        "exploration_percentage": (0.0, 0.3),
        "max_speed_and_length_factor": (1, 2.5),
        "average_edge_duration_factor": (1, 2.5),
        "freshness_update_factor": (5, 20),
        "freshness_cut_off_value": (100, 700),
        "re_route_every_ticks": (10, 70)
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
        "topic": "crowd-nav-performance",
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


def evaluator(result_state, wf):
    # Here, we need to decide either to return a single value or a tuple
    # depending of course on what the optimizer can handle
    return result_state["avg_overhead"] + result_state["avg_performance"]


def state_initializer(state, wf):
    state["count_performance"] = 0
    state["count_overhead"] = 0
    state["avg_overhead"] = 0
    state["avg_performance"] = 0
    return state