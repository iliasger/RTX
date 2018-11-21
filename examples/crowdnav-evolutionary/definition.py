# Evolutionary search for knob values
name = "CrowdNav-Evolutionary"

execution_strategy = {
    "parallel_execution_of_individuals": False, # if this is True, CrowdNav should be run with 'python parallel.py <no>'
    # where <no> is equal to the "population_size" below
    # the parallel execution creates as many processes as the "population_size" below
    # the non-parallel execution runs everything in the same process.. (good for debugging!)
    "ignore_first_n_results": 20, #10000,
    "sample_size": 20, #10000,
    "type": "evolutionary",
    "optimizer_method": "NSGAII", # "GA"
    "optimizer_iterations": 4, # number of generations
    "population_size": 3, # number of individuals in the population
    "offspring_size" : 3, # typically equals the population size
    "crossover_probability": 0.5,
    "mutation_probability": 0.2,
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


def primary_data_reducer(state, newData, wf):
    cnt = state["count"]
    state["avg_overhead"] = (state["avg_overhead"] * cnt + newData["overhead"]) / (cnt + 1)
    state["count"] = cnt + 1
    return state


primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-trips",
    "serializer": "JSON",
    "data_reducer": primary_data_reducer
}


change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-commands",
    "serializer": "JSON",
}


# defines what the experimentFunction returns
def evaluator(resultState, wf):
    # avg oveahead computed by primary_data_reducer
    return resultState["avg_overhead"]


def state_initializer(state, wf):
    state["count"] = 0
    state["avg_overhead"] = 0
    return state
