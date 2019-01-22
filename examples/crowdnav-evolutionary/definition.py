import multiprocessing as mpc
from time import sleep
from numpy import median

# Evolutionary search for knob values
name = "CrowdNav-Evolutionary"
processor_id = 0

execution_strategy = {
    "parallel_execution_of_individuals": False, # if this is True, CrowdNav should be run with 'python parallel.py <no>'
    # where <no> is equal to the "population_size" below
    # the parallel execution creates as many processes as the "population_size" below
    # the non-parallel execution runs everything in the same process.. (good for debugging!)
    "ignore_first_n_results": 0,  #10000,
    "sample_size": 5000,  #10000,
    "type": "evolutionary",
    # Options: NSGAII, GA, NoveltySearch, RandomSearch
    "optimizer_method": "RandomSearch",  # "GA"  "NoveltySearch"
    "is_multi_objective": True,
    "optimizer_iterations": 10,  # number of generations
    "population_size": 10,      # number of individuals in the population
    "offspring_size": 10,        # typically equals the population size
    "crossover_probability": 0.7,
    "mutation_probability": 0.3,
    "novelty_archive_percent": 0.2, # % of population to keep in the archive
    "fitness_weight":0.25,          # linear weighted sum for novelty metric
    "novelty_weight":0.75,          # linear weighted sum for novelty metric
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
    state["overheads"].append(new_data["overhead"])
    return state


def routing_performance_data_reducer(state, new_data, wf):
    state["routings"].append(new_data["duration"])
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
        "topic": "crowd-nav-routing",
        "serializer": "JSON",
        "data_reducer": routing_performance_data_reducer
    }
]

change_provider = {
    "type": "kafka_producer",
    "kafka_uri": "localhost:9092",
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

    data_to_save["median_overhead"] = median(result_state["overheads"])
    data_to_save["median_routing"] = median(result_state["routings"])

    wf.db.save_data_for_experiment(wf.iteration_id, wf.current_knobs, data_to_save, wf.rtx_run_id, wf.individual_id)

    return data_to_save["median_overhead"], data_to_save["median_routing"]



def state_initializer(state, wf):
    state["overheads"] = []
    state["routings"] = []
    state["count_routing"] = 0
    state["count_overhead"] = 0
    state["avg_overhead"] = 0
    state["avg_routing"] = 0
    return state
