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

from rtxlib.changeproviders import init_change_provider
from rtxlib.dataproviders import init_data_providers


def start_evolutionary_strategy(wf):
    global original_primary_data_provider_topic
    global original_change_provider_topic

    info("> ExecStrategy   | Evolutionary", Fore.CYAN)
    optimizer_method = wf.execution_strategy["optimizer_method"]
    wf.totalExperiments = wf.execution_strategy["optimizer_iterations"]
    info("> Optimizer      | " + optimizer_method, Fore.CYAN)

    original_primary_data_provider_topic = wf.primary_data_provider["instance"].topic
    original_change_provider_topic = wf.change_provider["instance"].topic

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


def random_knob_config(variables, range_tuples):
    knob_config = []
    for x, tuble in zip(variables, range_tuples):
        if x == "route_random_sigma" or x == "exploration_percentage" \
                or x == "max_speed_and_length_factor" or x == "average_edge_duration_factor":
            value = random.uniform(tuble[0], tuble[1])
            value = round(value, 2)
            knob_config.append(value)
        elif x == "freshness_update_factor" or x == "freshness_cut_off_value" \
                or x == "re_route_every_ticks":
            value = random.randint(tuble[0], tuble[1])
            knob_config.append(value)
    return creator.Individual(knob_config)


def mutate(individual, variables, range_tubles):
    i = random.randint(0, len(individual) - 1)
    if variables[i] == "route_random_sigma" or variables[i] == "exploration_percentage" \
            or variables[i] == "max_speed_and_length_factor" or variables[i] == "average_edge_duration_factor":
        value = random.uniform(range_tubles[i][0], range_tubles[i][1])
        value = round(value, 2)
        individual[i] = value
    elif variables[i] == "freshness_update_factor" or variables[i] == "freshness_cut_off_value" \
            or variables[i] == "re_route_every_ticks":
        value = random.randint(range_tubles[i][0], range_tubles[i][1])
        individual[i] = value
    return individual,


def evaluate(individual_and_id, vars, ranges, wf):
    # we recreate here the instances of the change provider and data provider that we deleted before
    init_change_provider(wf)
    init_data_providers(wf)
    result = evolutionary_execution(wf, individual_and_id, vars)
    info("> RESULT: " + str(result), Fore.RED)
    return result,


def evolutionary_execution(wf, individual_and_id, variables):

    opti_values = individual_and_id[0]
    crowdnav_id = individual_and_id[1]
    """ this is the function we call and that returns a value for optimization """
    knob_object = recreate_knob_from_optimizer_values(variables, opti_values)
    # create a new experiment to run in execution
    exp = dict()

    # TODO where do we start multiple threads to call the experimentFunction concurrently, once for each experiment and crowdnav instance?
    # TODO should we create new/fresh CrowdNav instances for each iteration/generation? Otherwise, we use the same instance to evaluate across interations/generations to evaluate individiuals.

    suffix = ""
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        suffix = "-" + str(crowdnav_id)

    wf.primary_data_provider["instance"].topic = original_primary_data_provider_topic + suffix
    wf.change_provider["instance"].topic = original_change_provider_topic + suffix
    info("Listening to " + wf.primary_data_provider["instance"].topic)
    info("Posting changes to " + wf.change_provider["instance"].topic)

    exp["ignore_first_n_results"] = wf.execution_strategy["ignore_first_n_results"]
    exp["sample_size"] = wf.execution_strategy["sample_size"]
    exp["knobs"] = knob_object
    # the experiment function returns what the evaluator in definition.py is computing
    return experimentFunction(wf, exp)


def recreate_knob_from_optimizer_values(variables, opti_values):
    """ recreates knob values from a variable """
    knob_object = {}
    # create the knobObject based on the position of the opti_values and variables in their array
    for idx, val in enumerate(variables):
        knob_object[val] = opti_values[idx]
    info(">> knob object " + str(knob_object))
    return knob_object
