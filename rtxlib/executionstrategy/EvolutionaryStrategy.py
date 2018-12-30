#
# To run multiple instance of CrowdNav in parallel to concurrently evaluate multiple individuals,
# use the "parallel" branch of CrowdNav and start CrowdNav with: python parallel.py <number of instances>.
# This fires up <number of instances> CrowdNav instances in headless mode. Each instance uses a different
# Kafka topic such as:
# crowd-nav-trips-0, crowd-nav-trips-1, crowd-nav-trips-2, ...
# crowd-nav-commands-0, crowd-nav-commands-1, crowd-nav-commands-2, ...
# where the number refers to the an instance of CrowdNav.
#

from colorama import Fore

from rtxlib import info, error
from rtxlib.execution import experimentFunction

import random
from deap import base, creator

from ga import ga
from nsga2 import nsga2
from novelty_search import novelty_search
from random_search import random_search

from rtxlib.changeproviders import init_change_provider
from rtxlib.dataproviders import init_data_providers


def start_evolutionary_strategy(wf):
    global original_primary_data_provider_topic
    global original_secondary_data_provider_topic
    global original_change_provider_topic

    info("> ExecStrategy   | Evolutionary", Fore.CYAN)
    optimizer_method = wf.execution_strategy["optimizer_method"]
    wf.totalExperiments = wf.execution_strategy["optimizer_iterations"]
    info("> Optimizer      | " + optimizer_method, Fore.CYAN)

    original_primary_data_provider_topic = wf.primary_data_provider["topic"]
    original_secondary_data_provider_topic = wf.secondary_data_providers[0]["topic"]
    original_change_provider_topic = wf.change_provider["topic"]

    # we look at the ranges the user has specified in the knobs
    knobs = wf.execution_strategy["knobs"]
    # we create a list of variable/knob names and a list of ranges (from,to) for each knob
    variables = []
    range_tuples = []
    # we fill the arrays and use the index to map from gauss-optimizer-value to variable
    for key in knobs:
        variables += [key]
        range_tuples += [(knobs[key][0], knobs[key][1])]

    info("> Run Optimizer | " + optimizer_method, Fore.CYAN)
    if optimizer_method == "GA":
        ga(variables, range_tuples, random_knob_config, mutate, evaluate, wf)
    elif optimizer_method == "NSGAII":
        nsga2(variables, range_tuples, random_knob_config, mutate, evaluate, wf)
    elif optimizer_method == "NoveltySearch":
        novelty_search(variables, range_tuples, random_knob_config, mutate, evaluate, wf)
    elif optimizer_method == "RandomSearch":
        random_search(variables, range_tuples, random_knob_config, mutate, evaluate, wf)


def random_knob_config(variables, range_tuples):
    knob_config = []
    for x, range_tuple in zip(variables, range_tuples):
        if x == "route_random_sigma" or x == "exploration_percentage" \
                or x == "max_speed_and_length_factor" or x == "average_edge_duration_factor":
            value = random.uniform(range_tuple[0], range_tuple[1])
            value = round(value, 2)
            knob_config.append(value)
        elif x == "freshness_update_factor" or x == "freshness_cut_off_value" \
                or x == "re_route_every_ticks":
            value = random.randint(range_tuple[0], range_tuple[1])
            knob_config.append(value)
    return creator.Individual(knob_config)


def mutate(individual, variables, range_tuples):
    i = random.randint(0, len(individual) - 1)
    if variables[i] == "route_random_sigma" or variables[i] == "exploration_percentage" \
            or variables[i] == "max_speed_and_length_factor" or variables[i] == "average_edge_duration_factor":
        value = random.uniform(range_tuples[i][0], range_tuples[i][1])
        value = round(value, 2)
        individual[i] = value
    elif variables[i] == "freshness_update_factor" or variables[i] == "freshness_cut_off_value" \
            or variables[i] == "re_route_every_ticks":
        value = random.randint(range_tuples[i][0], range_tuples[i][1])
        individual[i] = value
    return individual,


# reuse earlier fitness results if the same individual should be evaluated again
# however and currently, identical individuals generated in the same iteration are evaluated concurrently, and
# more than once.
#
# key is the String representation of the individual (sequences cannot be keys), value is the fitness
_fitnesses = dict()


def evaluate(individual_and_id, vars, ranges, wf):
    individual = individual_and_id[0]
    # retrieve fitness from dict (earlier evaluation)
    fitness = _fitnesses.get(str(individual), None)

    if fitness is None:
        info("> Compute fitness for the individual " + str(individual) + " ...")
        # fitness of the individual is unknown, so compute it and add it to the dict
        # we recreate here the instances of the change provider and data provider that we deleted before
        update_topics(wf, individual_and_id[1])
        init_change_provider(wf)
        init_data_providers(wf)
        fitness = evolutionary_execution(wf, individual, vars)
        _fitnesses[str(individual)] = fitness
    else:
        info("> Reuse fitness " + str(fitness) + " from earlier evaluation for the individual "
             + str(individual) + " ...")
        reuse_evaluation(wf, individual, individual_and_id[1], vars, fitness)

    if wf.execution_strategy["is_multi_objective"]:
        # fitness is a tuple (avg trip overhead, avg performance)
        info("> FITNESS: " + str(fitness), Fore.RED)
        return fitness
    else:
        # just return the trip overhead
        info("> FITNESS: " + str(fitness[0]), Fore.RED)
        return fitness[0],


def evolutionary_execution(wf, opti_values, variables):
    # Where do we start multiple threads to call the experimentFunction concurrently,
    # once for each experiment and crowdnav instance?
    # This method can be invoked concurrently.

    """ this is the function we call and that returns a value for optimization """
    knob_object = recreate_knob_from_optimizer_values(variables, opti_values)
    # create a new experiment to run in execution
    exp = dict()
    exp["ignore_first_n_results"] = wf.execution_strategy["ignore_first_n_results"]
    exp["sample_size"] = wf.execution_strategy["sample_size"]
    exp["knobs"] = knob_object
    # the experiment function returns what the evaluator in definition.py is computing
    return experimentFunction(wf, exp)


def update_topics(wf, crowdnav_id):
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        suffix = "-" + str(crowdnav_id)
        wf.processor_id = crowdnav_id
    else:
        suffix = "-0"

    wf.primary_data_provider["topic"] = original_primary_data_provider_topic + suffix
    wf.secondary_data_providers[0]["topic"] = original_secondary_data_provider_topic + suffix
    wf.change_provider["topic"] = original_change_provider_topic + suffix

    info("Listening to " + wf.primary_data_provider["topic"])
    info("Listening to " + wf.secondary_data_providers[0]["topic"])
    info("Posting changes to " + wf.change_provider["topic"])


def recreate_knob_from_optimizer_values(variables, opti_values):
    """ recreates knob values from a variable """
    knob_object = {}
    # create the knobObject based on the position of the opti_values and variables in their array
    for idx, val in enumerate(variables):
        knob_object[val] = opti_values[idx]
    info(">> knob object " + str(knob_object))
    return knob_object


def reuse_evaluation(wf, opti_values, individual_id, vars, fitness):
    wf.experimentCounter += 1
    wf.processor_id = individual_id
    wf.current_knobs = recreate_knob_from_optimizer_values(vars, opti_values)
    data_to_save = {}
    data_to_save["avg_overhead"] = fitness[0]
    data_to_save["avg_routing"] = fitness[1]
    data_to_save["overheads"] = [-1]
    data_to_save["routings"] = [-1]
    wf.db.save_data_for_experiment(wf.experimentCounter, wf.current_knobs, data_to_save, wf.rtx_run_id, wf.processor_id)
    # Here, we need to decide either to return a single value or a tuple
    # depending of course on what the optimizer can handle
    return data_to_save["avg_overhead"], data_to_save["avg_routing"]