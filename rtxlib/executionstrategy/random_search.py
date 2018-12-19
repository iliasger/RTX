#
# Random search algorithm.  
# Adapted from the DEAP tutorial: https://deap.readthedocs.io/en/master/overview.html
#

# The number of random individuals is calculated by multiplying population size by number of generations.
# If the number of required CrowdNav instances is too large, this could be batched instead when running
# experiments (i.e., run 50 at a time instead of 500 at a time).  If that is the case, ensure the seed is
# updated appropriatelye.


import pathos
import random
import numpy as np
import operator

from rtxlib import info, error
from deap import tools, base, creator
from collections import defaultdict
from colorama import Fore

def random_search(variables, range_tuples, init_individual, mutate, evaluate, wf):
    random.seed()

    # parameters
    optimizer_iterations  = wf.execution_strategy["optimizer_iterations"]
    population_size       = wf.execution_strategy["population_size"] * optimizer_iterations # No evolution, just run all

    info("> Parameters:\noptimizer_iterations: " + str(optimizer_iterations)  + \
         "\npopulation_size:  "                  + str(population_size)) 

    #creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("FitnessMin", base.Fitness, weights=(-100.0, -10))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register("individual", init_individual, variables=variables, range_tuples=range_tuples)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    pop = toolbox.population(n=population_size)

    info("Variables: " + str(variables))
    info("Population: " + str(pop))

    # we need to delete these entries since they cannot be serialized
    del wf.change_provider["instance"]
    del wf.primary_data_provider["instance"]
    del wf.secondary_data_providers[0]["instance"]

    toolbox.register("evaluate", evaluate, vars=variables, ranges=range_tuples, wf=wf)

    # Evaluate the entire population
    number_individuals_to_evaluate_in_parallel = wf.execution_strategy["population_size"]
    pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate_in_parallel)
    zipped = zip(pop, range(number_individuals_to_evaluate_in_parallel))
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        fitnesses = pool.map(toolbox.evaluate, zipped)
    else:
        fitnesses = map(toolbox.evaluate, zipped)

    for ind, fit in zip(pop, fitnesses):
        info("> " + str(ind) + " -- " + str(fit))
        ind.fitness.values = fit


    # The population is entirely replaced by the offspring
    info("> Population: " + str(pop))
    info("> Individual: " + str(variables))
