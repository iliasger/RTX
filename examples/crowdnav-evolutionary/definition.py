# Evolutionary search for knob values
name = "CrowdNav-Evolutionary"

execution_strategy = {
    "parallel_execution_of_individuals": True, # if this is True, CrowdNav should be run with 'python parallel.py <no>'
    # where <no> is equal to the "population_size" below
    # the parallel execution creates as many processes as the "population_size" below
    # the non-parallel execution runs everything in the same process.. (good for debugging!)
    "ignore_first_n_results": 5,  #10000,
    "sample_size": 10,  #10000,
    "type": "evolutionary",
    # Options: NSGAII, GA, NoveltySearch, RandomSearch
    "optimizer_method": "RandomSearch",  # "GA"  "NoveltySearch"
    "is_multi_objective": True,
    "optimizer_iterations": 1,  # number of generations
    "population_size": 5,      # number of individuals in the population
    "offspring_size": 5,        # typically equals the population size
    "crossover_probability": 0.7,
    "mutation_probability": 0.3,
    "novelty_archive_percent": 0.2,
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


def overhead_data_reducer(state, new_data, wf):
    cnt = state["count_overhead"]
    # TODO check how the data is saved from multiple data reducers esp. the secondary ones
    wf.db.save_data_point(wf.experimentCounter, wf.current_knobs, new_data, state["count_overhead"], wf.rtx_run_id)
    state["avg_overhead"] = (state["avg_overhead"] * cnt + new_data["overhead"]) / (cnt + 1)
    state["count_overhead"] = cnt + 1
    return state


def performance_data_reducer(state, new_data, wf):
    cnt = state["count_performance"]
    # TODO check how the data is saved from multiple data reducers esp. the secondary ones
    wf.db.save_data_point(wf.experimentCounter, wf.current_knobs, new_data, state["count_performance"], wf.rtx_run_id)
    state["avg_performance"] = (state["avg_performance"] * cnt + new_data["duration"]) / (cnt + 1)
    state["count_performance"] = cnt + 1
    return state


primary_data_provider = {
    "type": "kafka_consumer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-trips",
    "serializer": "JSON",
    "data_reducer": overhead_data_reducer
}

secondary_data_providers = [
    {
        "type": "kafka_consumer",
        "kafka_uri": "localhost:9092",
        "topic": "crowd-nav-performance",
        "serializer": "JSON",
        "data_reducer": performance_data_reducer
    }
]

change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "localhost:9092",
    "topic": "crowd-nav-commands",
    "serializer": "JSON",
}


def evaluator(result_state, wf):
    # Here, we need to decide either to return a single value or a tuple
    # depending of course on what the optimizer can handle
    return result_state["avg_overhead"], result_state["avg_performance"]


def state_initializer(state, wf):
    state["count_performance"] = 0
    state["count_overhead"] = 0
    state["avg_overhead"] = 0
    state["avg_performance"] = 0
    return state
