#
# The GA from the DEAP tutorial: https://deap.readthedocs.io/en/master/overview.html
#

import pathos
import random

from rtxlib import info, error
from deap import tools, base, creator


def ga(variables, range_tuples, init_individual, mutate, evaluate, wf):
    random.seed()

    optimizer_iterations = wf.execution_strategy["optimizer_iterations"]
    population_size = wf.execution_strategy["population_size"]
    crossover_probability = wf.execution_strategy["crossover_probability"]
    mutation_probability = wf.execution_strategy["mutation_probability"]
    info("> Parameters:\noptimizer_iterations: " + str(optimizer_iterations) + "\npopulation_size: " + str(
        population_size) + "\ncrossover_probability: " + str(crossover_probability) + "\nmutation_probability: " + str(
        mutation_probability))

    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register("individual", init_individual, variables=variables, range_tuples=range_tuples)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    pop = toolbox.population(n=population_size)

    info("Variables: " + str(variables))
    info("Population: " + str(pop))

    toolbox.register("mate", tools.cxOnePoint)
    toolbox.register("mutate", mutate, variables=variables, range_tubles=range_tuples)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # we need to delete these entries since they cannot be serialized
    del wf.change_provider["instance"]
    del wf.primary_data_provider["instance"]

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

    for g in range(optimizer_iterations):
        info("> \n" + str(g) + ". Generation")
        # Select the next generation individuals
        offspring = toolbox.select(pop, len(pop))
        # Clone the selected individuals
        offspring = map(toolbox.clone, offspring)

        # Apply crossover and mutation on the offspring
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < crossover_probability:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values

        for mutant in offspring:
            if random.random() < mutation_probability:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        zipped = zip(invalid_ind,range(number_individuals_to_evaluate_in_parallel))
        if wf.execution_strategy["parallel_execution_of_individuals"]:
            fitnesses = pool.map(toolbox.evaluate, zipped)
        else:
            fitnesses = map(toolbox.evaluate, zipped)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        # The population is entirely replaced by the offspring
        pop[:] = offspring
        info("> Population: " + str(pop))
        info("> Individual: " + str(variables))
