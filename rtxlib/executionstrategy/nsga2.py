import pathos
import random
import numpy

from rtxlib import info, error
from deap import tools, base, creator

debug = False
verbose = True


def nsga2(variables, range_tuples, init_individual, mutate, evaluate, wf):
    random.seed()

    optimizer_iterations = wf.execution_strategy["optimizer_iterations"]
    population_size = wf.execution_strategy["population_size"]
    offspring_size = wf.execution_strategy["offspring_size"]
    crossover_probability = wf.execution_strategy["crossover_probability"]
    mutation_probability = wf.execution_strategy["mutation_probability"]

    info("> Parameters:\noptimizer_iterations: " + str(optimizer_iterations) + "\npopulation_size: " + str(
        population_size) + "\noffspring_size: " + str(offspring_size) + "\ncrossover_probability: " + str(
        crossover_probability) + "\nmutation_probability: " + str(
        mutation_probability))

    creator.create("FitnessMin", base.Fitness, weights=(-100.0, -10))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()

    toolbox.register("individual", init_individual, variables=variables, range_tuples=range_tuples)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    toolbox.register("mate", tools.cxUniform, indpb=0.5)

    toolbox.register("mutate", mutate, variables=variables, range_tuples=range_tuples)

    toolbox.register("select", tools.selNSGA2)

    # we need to delete these entries since they cannot be serialized
    del wf.change_provider["instance"]
    del wf.primary_data_provider["instance"]
    del wf.secondary_data_providers[0]["instance"]

    toolbox.register("evaluate", evaluate, vars=variables, ranges=range_tuples, wf=wf)

    # log the history
    history = tools.History()
    # Decorate the variation operators
    toolbox.decorate("mate", history.decorator)
    toolbox.decorate("mutate", history.decorator)

    # initializing the population
    info("Init the population")
    population = toolbox.population(n=population_size)

    # update history
    history.update(population)
    # init hall of fame
    hall_of_fame = tools.ParetoFront()

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    # axis = 0, the numpy.mean will return an array of results
    stats.register("avg", numpy.mean, axis=0)
    stats.register("std", numpy.std, axis=0)
    stats.register("min", numpy.min, axis=0)
    stats.register("max", numpy.max, axis=0)
    stats.register("pop_fitness", return_as_is)

    logbook = tools.Logbook()
    logbook.header = ['gen', 'nevals'] + (stats.fields if stats else [])

    #############
    # evolve
    #############

    # Evaluate the entire population - no individual has a fitness yet
    number_individuals_to_evaluate_in_parallel = wf.execution_strategy["population_size"]
    pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate_in_parallel)
    zipped = zip(population, range(number_individuals_to_evaluate_in_parallel))
    if wf.execution_strategy["parallel_execution_of_individuals"]:
        fitnesses = pool.map(toolbox.evaluate, zipped)
    else:
        fitnesses = map(toolbox.evaluate, zipped)
    # assign fitness to individuals
    for ind, fit in zip(population, fitnesses):
        ind.fitness.values = fit

    if hall_of_fame is not None:
        hall_of_fame.update(population)

    record = stats.compile(population) if stats is not None else {}
    logbook.record(gen=0, nevals=len(population), **record)
    if verbose:
        info(logbook.stream)

    # for each iteration/generation
    for gen in range(1, optimizer_iterations + 1):
        if debug:
            info("\n" + str(gen) + ". Generation")
            info("Population    : " + str(population))

        # Vary the population
        offspring = vary(population, toolbox, offspring_size, crossover_probability, mutation_probability)
        if debug:
            info("Offspring     : " + str(offspring))

        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        number_individuals_to_evaluate_in_parallel = len(invalid_ind)
        pool = pathos.multiprocessing.ProcessPool(number_individuals_to_evaluate_in_parallel)
        zipped = zip(invalid_ind, range(number_individuals_to_evaluate_in_parallel))
        if wf.execution_strategy["parallel_execution_of_individuals"]:
            fitnesses = pool.map(toolbox.evaluate, zipped)
        else:
            fitnesses = map(toolbox.evaluate, zipped)

        # assign fitness to individuals
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        # Update the hall of fame with the generated individuals
        if hall_of_fame is not None:
            hall_of_fame.update(offspring)

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

        # Update the statistics with the new population
        record = stats.compile(population) if stats is not None else {}
        logbook.record(gen=gen, nevals=len(invalid_ind), **record)
        if verbose:
            info(logbook.stream)

    info("\nDONE\n")
    info("Population: " + str(population))
    info("Hall of Fame: " + str(hall_of_fame))


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
