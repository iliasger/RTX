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

debug = False
verbose = True

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

    offspring_size = wf.execution_strategy["offspring_size"]



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

    population = toolbox.population(n=population_size)

    info("Variables: " + str(variables))
    info("Population: " + str(population))

    toolbox.register("mate", tools.cxOnePoint)
    toolbox.register("mutate", mutate, variables=variables, range_tuples=range_tuples)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # we need to delete these entries since they cannot be serialized
    del wf.change_provider["instance"]
    del wf.primary_data_provider["instance"]
    del wf.secondary_data_providers[0]["instance"]

    # log the history
    history = tools.History()
    # Decorate the variation operators
    toolbox.decorate("mate", history.decorator)
    toolbox.decorate("mutate", history.decorator)

    toolbox.register("evaluate", evaluate, vars=variables, ranges=range_tuples, wf=wf)

    # update history
    history.update(population)

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    # axis = 0, the numpy.mean will return an array of results
    stats.register("avg", np.mean, axis=0)
    stats.register("std", np.std, axis=0)
    stats.register("min", np.min, axis=0)
    stats.register("max", np.max, axis=0)
    stats.register("pop_fitness", return_as_is)

    logbook = tools.Logbook()
    logbook.header = ['gen', 'nevals'] + (stats.fields if stats else [])

    # Evaluate the entire population
    number_individuals_to_evaluate_in_parallel = wf.execution_strategy["population_size"]
    zipped = zip(population, range(number_individuals_to_evaluate_in_parallel), [0]*number_individuals_to_evaluate_in_parallel)
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate_in_parallel)
        fitnesses = pool.map(toolbox.evaluate, zipped)
    else:
        fitnesses = map(toolbox.evaluate, zipped)

    for ind, fit in zip(population, fitnesses):
        info("> " + str(ind) + " -- " + str(fit))
        ind.fitness.values = fit

    # Calculate initial novelty archive
    novelty_archive = calculate_novelty(0, population, novelty_archive_k, novelty_archive, novelty_weight, fitness_weight)
    record = stats.compile(population) if stats is not None else {}
    logbook.record(gen=0, nevals=len(population), **record)
    if verbose:
        info(logbook.stream)

    for gen in range(1, optimizer_iterations):
        if debug:
            info("\n" + str(gen) + ". Generation")
            info("Population    : " + str(population))

        # Vary the population
        offspring = vary(population, toolbox, offspring_size, crossover_probability, mutation_probability)
        if debug:
            info("Offspring     : " + str(offspring))

        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        number_individuals_to_evaluate = len(invalid_ind)
        zipped = zip(invalid_ind, range(number_individuals_to_evaluate), [gen]*number_individuals_to_evaluate)
        if wf.execution_strategy["parallel_execution_of_individuals"]:
            # TODO in each generation, a new pool is created. What about the pool created in the previous run(s)?
            pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate)
            fitnesses = pool.map(toolbox.evaluate, zipped)
        else:
            fitnesses = map(toolbox.evaluate, zipped)

        # assign fitness to individuals
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        # Update the hall of fame with the generated individuals
#        if hall_of_fame is not None:
#            hall_of_fame.update(offspring)

        # Select the next generation population
        population[:] = toolbox.select(population + offspring, population_size)
        if debug:
            info("New Population: " + str(population))

        if debug:
            for i in range(len(population)):
                for j in range(i, len(population)):
                    if i != j:
                        dup = is_duplicate(population[i], population[j])
                        if dup:
                            info("Duplicate individuals #" + str(i) + " and #" + str(j))
        novelty_archive = calculate_novelty(gen, population, novelty_archive_k, novelty_archive, novelty_weight, fitness_weight)

        # The population is entirely replaced by the offspring
        population[:] = offspring
        info("> Population: " + str(population))
        info("> Individual: " + str(variables))
        info("> Novelty archive: " + str(novelty_archive))

        # Update the statistics with the new population
        record = stats.compile(population) if stats is not None else {}
        record['novelty_archive'] = novelty_archive

        logbook.record(gen=gen, nevals=len(invalid_ind), **record)
        if verbose:
            info(logbook.stream)
        """
        # This is the old version where we weren't getting full evaluation.  It can be removed once we verify that everything is OK

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
        # TODO should number_individuals_to_evaluate_in_parallel be set to len(invalid_ind)?
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
        """

        # TODO : debugging
        with open(filename, 'a') as f:
          f.write("Generation %d\n" % gen)
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

def vary(population, toolbox, lambda_, cxpb, mutpb):
    assert (cxpb + mutpb) <= 1.0, ("The sum of the crossover and mutation probabilities must be smaller or equal to "
                                   "1.0.")

    offspring = []
    for _ in xrange(lambda_):
        op_choice = random.random()
        if op_choice < cxpb:  # Apply crossover
            ind1, ind2 = map(toolbox.clone, random.sample(population, 2))
            msg = str(ind1) + " x " + str(ind2)
            ind1, ind2 = toolbox.mate(ind1, ind2)
            del ind1.fitness.values
            offspring.append(ind1)
            if debug:
                info("Obtained by crossover " + str(ind1) + " from " + msg)
        elif op_choice < cxpb + mutpb:  # Apply mutation
            ind = toolbox.clone(random.choice(population))
            msg = str(ind)
            ind, = toolbox.mutate(ind)
            del ind.fitness.values
            offspring.append(ind)
            if debug:
                info("Obtained by mutation " + str(ind) + " from " + msg)
        else:  # Apply reproduction
            offspring.append(random.choice(population))

    return offspring


def return_as_is(a):
    return a


def is_duplicate(ind1, ind2):
    for i in range(len(ind1)):
        if ind1[i] != ind2[i]:
            return False

    return True
