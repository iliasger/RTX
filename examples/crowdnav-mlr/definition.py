name = "MLR-MBO bayesian optimization"
id = 1

execution_strategy = {
    "ignore_first_n_results": 3,
    "sample_size": 20,
    "type": "mlr_mbo",
    "optimizer_iterations": 5,
    "optimizer_iterations_in_design": 10,
    "population_size": 5,
    "acquisition_method": "aei",  # mr, se, cb, aei, eqi. check http://mlrmbo.mlr-org.com/reference/infillcrits.html
    "knobs": {
        "route_random_sigma": (0.0, 1.0)
    }
}


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
    return resultState["avg_overhead"]


def state_initializer(state, wf):
    state["count"] = 0
    state["avg_overhead"] = 0
    return state
