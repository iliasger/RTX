#
# Novelty search algorithm.  Adapted from:
# the GA from the DEAP tutorial: https://deap.readthedocs.io/en/master/overview.html
#

# TODO: ensure that fitness values aren't overriding novelty as 'the metric'

import pathos
import random
import numpy as np
import operator

from rtxlib import info, error
from deap import tools, base, creator
from collections import defaultdict
from colorama import Fore

def novelty_search(variables, range_tuples, init_individual, mutate, evaluate, wf):
    # TODO - debug
    filename = "NS-tmp.txt"

    random.seed()

    optimizer_iterations  = wf.execution_strategy["optimizer_iterations"]
    population_size       = wf.execution_strategy["population_size"]
    crossover_probability = wf.execution_strategy["crossover_probability"]
    mutation_probability  = wf.execution_strategy["mutation_probability"]

    fitness_weight        = wf.execution_strategy["fitness_weight"]
    novelty_weight        = wf.execution_strategy["novelty_weight"]



    # Novelty parameters
    novelty_archive_perc = wf.execution_strategy["novelty_archive_percent"]
    novelty_archive_k    = int(novelty_archive_perc * population_size)
    if (novelty_archive_k == 0):
      novelty_archive_k = 5
    novelty_archive = []

    info("> Parameters:\noptimizer_iterations: " + str(optimizer_iterations)  + \
         "\npopulation_size:  "                  + str(population_size)       + \
         "\ncrossover_probability: "             + str(crossover_probability) + \
         "\nmutation_probability: "              + str(mutation_probability)  + \
         "\nnovelty_archive_perc: "              + str(novelty_archive_perc)  + \
         "\nnovelty_archive_k: "                 + str(novelty_archive_k))

    creator.create("FitnessMin", base.Fitness, weights=(-100.0, -10))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register("individual", init_individual, variables=variables, range_tuples=range_tuples)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    pop = toolbox.population(n=population_size)

    info("Variables: " + str(variables))
    info("Population: " + str(pop))

    toolbox.register("mate", tools.cxOnePoint)
    toolbox.register("mutate", mutate, variables=variables, range_tuples=range_tuples)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # we need to delete these entries since they cannot be serialized
    del wf.change_provider["instance"]
    del wf.primary_data_provider["instance"]
    del wf.secondary_data_providers[0]["instance"]

    toolbox.register("evaluate", evaluate, vars=variables, ranges=range_tuples, wf=wf)

    # Evaluate the entire population
    number_individuals_to_evaluate_in_parallel = wf.execution_strategy["population_size"]
    pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate_in_parallel)
    zipped = zip(pop, range(number_individuals_to_evaluate_in_parallel), [0]*number_individuals_to_evaluate_in_parallel)
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        fitnesses = pool.map(toolbox.evaluate, zipped)
    else:
        fitnesses = map(toolbox.evaluate, zipped)

    for ind, fit in zip(pop, fitnesses):
        info("> " + str(ind) + " -- " + str(fit))
        ind.fitness.values = fit

    # Calculate initial novelty archive
    novelty_archive = calculate_novelty(0, pop, novelty_archive_k, novelty_archive, novelty_weight, fitness_weight)

    for g in range(1, optimizer_iterations):
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
        zipped = zip(invalid_ind,range(number_individuals_to_evaluate_in_parallel), [g]*number_individuals_to_evaluate_in_parallel)
        if wf.execution_strategy["parallel_execution_of_individuals"]:
            fitnesses = pool.map(toolbox.evaluate, zipped)
        else:
            fitnesses = map(toolbox.evaluate, zipped)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit



        # TODO - do we need to overwrite fitness?
        novelty_archive = calculate_novelty(g, pop, novelty_archive_k, novelty_archive, novelty_weight, fitness_weight)

        # The population is entirely replaced by the offspring
        pop[:] = offspring
        info("> Population: " + str(pop))
        info("> Individual: " + str(variables))
        info("> Novelty archive: " + str(novelty_archive))

        # TODO : debugging
        with open(filename, 'a') as f:
          f.write("Generation %d\n" % g)
          for na in novelty_archive:
            f.write("%s\n" % str(na))
          f.write("\n")


 
# Calculate pairwise novelty score between individuals in population,
# as well as to individuals in novelty archive
def calculate_novelty(generation, population, k, novelty_archive, novelty_weight, fitness_weight):
  novelties      = defaultdict(dict)
  novelty_scores = {}

  # Ensure we don't compare to ourselves and to one that has previously been computed
  # Duplicate a small amount of data to save an additional loop
  for i in range(len(population)):
    for j in range(len(population)):
      if (i is not j) and (j not in novelties[i]) and (i not in novelties[j]):
        ind1 = population[i]
        ind2 = population[j]
        novelties[i][j] = calculate_manhattan_distance(ind1, ind2)
        novelties[j][i] = novelties[i][j]  # Maintain a copy for easier lookup later

    # Calculate novelty score per individual
    novelties_sum = 0.0
    for j in range(len(population)):
      if i is not j:
        novelties_sum += novelties[i][j]
    novelty_scores[i] = novelties_sum / float(len(population))

    # TODO: add weights to definition.py
    novelty_scores[i] = (novelty_weight * novelty_scores[i]) + (fitness_weight * population[i].fitness.values[0])

    # Override DEAP fitness with novelty metric
    new_tuple = (novelty_scores[i], population[i].fitness.values[1])
    population[i].fitness.values = new_tuple

    # Sort scores in descending order
    sorted_scores = sorted(novelty_scores.items(), key=lambda x: -x[1])

  # Archive top solutions
  for i in range(max(2, k)):
    ind = population[sorted_scores[i][0]]
    novelty_archive.append((generation, ind, sorted_scores[i][1]))

  for i in range(len(novelty_archive)):
    print novelty_archive[i]
    print novelty_archive[i][2]

    info("> NOVELTY SCORE [%d]: %f" % (i, novelty_archive[i][2]), Fore.RED)

  # Sort novelty archive and trim down to K
  sorted_novelty_archive = sorted(novelty_archive, key=lambda x: -x[2])
  novelty_archive = sorted_novelty_archive[:k]

  return novelty_archive

# Calculate Manhattan Distance metric between two 
# configurations of knob values
def calculate_manhattan_distance(ind1, ind2):
  ind1_a = np.array(ind1)
  ind2_a = np.array(ind2)
  return np.linalg.norm(ind1_a - ind2_a)
