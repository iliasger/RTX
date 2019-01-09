import json
import requests

from colorama import Fore

from rtxlib import info, error
from rtxlib.execution import experimentFunction

plumber_host = "localhost"
plumber_port = 8004
header = {"content-type": "application/json"}
host_with_port = "http://" + str(plumber_host) + ":" + str(plumber_port)
connection_err_msg = {"error": "Connection with R server is failed"}


def start_mlr_mbo_strategy(wf):

    """ executes a self optimizing strategy """
    info("> ExecStrategy   | MLR", Fore.CYAN)

    optimizer_iterations = wf.execution_strategy["optimizer_iterations"]
    optimizer_iterations_in_design = wf.execution_strategy["optimizer_iterations_in_design"]
    wf.totalExperiments = optimizer_iterations * wf.execution_strategy["population_size"] + optimizer_iterations_in_design
    if "acquisition_method" in wf.execution_strategy:
        acquisition_method = wf.execution_strategy["acquisition_method"]
    else:
        acquisition_method = "dib"
    if "objectives_number" in wf.execution_strategy:
        objectives_number = wf.execution_strategy["objectives_number"]
    else:
        objectives_number = 1
    population_size = wf.execution_strategy["population_size"]

    update_topics(wf)

    # we look at the ranges the user has specified in the knobs
    knobs = wf.execution_strategy["knobs"]
    knob_types = wf.execution_strategy["knob_types"]
    info("> Initial knobs   | " + str(knobs), Fore.CYAN)

    # we create a list of variable names and a list of knob (min, max)
    json_array = []
    for key in knobs:
        knob_object = dict()
        knob_object["name"] = key
        min_value = min(knobs[key][0], knobs[key][1])
        max_value = max(knobs[key][0], knobs[key][1])
        type = knob_types[key]
        knob_object["min"] = min_value
        knob_object["max"] = max_value
        knob_object["type"] = type
        json_array.append(knob_object)
    request_body = dict(
        id=wf.rtx_run_id,
        wf=dict(
            acquisition_method=acquisition_method,
            optimizer_iterations=optimizer_iterations,
            optimizer_iterations_in_design=optimizer_iterations_in_design,
            knobs=json_array,
            objectives_number=objectives_number,
            population_size=population_size
        )
    )
    result = initiate_mlr_mbo(wf, request_body, objectives_number)
    if result is not None:
        info("> ExecStrategy mlrMBO  | " + str(result), Fore.CYAN)
    else:
        error("> ExecStrategy mlrMBO  | error occurred, see the logs")

    # finished
    info(">")

''' initiates mlrMBO execution by sending variables in a HTTP POST request 
    return value of the request are proposals for the initial design, e.g.
    [
        ["52d32e11-d409-4d19-a55a-8e3889a0ade4"], --> res[0]
        [  --> res[1]
            {"route_random_sigma":0.0052,"exploration_percentage":1.1535},
            {"route_random_sigma":0.183,"exploration_percentage":1.532},
            {"route_random_sigma":0.2861,"exploration_percentage":1.4327}
        ]
    ]
'''
def initiate_mlr_mbo(wf, request_body, objectives_number):
    try:
        api = host_with_port + "/mlrMBO/initiate"
        r = requests.post(api, data=json.dumps(request_body), headers=header)
        res = r.json()
        if res[0] and res[1]:
            initial_design_knobs = res[1]
            initial_design_values = []
            for knob in initial_design_knobs:
                exp = create_experiment_tuple(wf, knob)
                if objectives_number == 1:
                    value = float(experimentFunction(wf, exp))
                else:
                    value = experimentFunction(wf, exp)
                initial_design_values.append(value)
            # now update the design with calculated outputs
            return update_initial_design(wf, initial_design_values, objectives_number)
        else:
            err_msg = {"error": "Cannot fetch initial design proposal/values, make sure R server is up and running"}
            error(err_msg)
            return None
    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


''' updates mlrMBO design by sending outputs in a HTTP POST request '''
def update_initial_design(wf, initial_design_values, objectives_number):
    try:
        body = dict(
            id=wf.rtx_run_id,
            initial_design_values=initial_design_values
        )
        api = host_with_port + "/mlrMBO/initialDesign/update"
        r = requests.post(api, data=json.dumps(body), headers=header)
        res = r.json()
        if "result" in res:
            if res["result"] is True:
                # if it reaches this point, then initial state is done, we should create artifacts
                return create_artifacts(wf, objectives_number)
            else:
                err_msg = {"error": res["result"]}
                error(err_msg)
                return None
        else:
            err_msg = {"error": "Cannot update initial design values, make sure R server is up and running"}
            error(err_msg)
            return None
    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


''' triggers R side to create acquisition criteria & MBO controll and calls initSMBO function '''
def create_artifacts(wf, objectives_number):
    try:
        # keeps track of all knobs that have been used in experimentation and find best one
        knobs_and_results = []
        body = dict(
            id=wf.rtx_run_id
        )
        api = host_with_port + "/mlrMBO/createArtifacts"
        r = requests.post(api, data=json.dumps(body), headers=header)
        res = r.json()
        if "result" in res:
            if res["result"] is True:
                # if it reaches this point, then mlrMBO is started to propose points,
                # so we run experimentFunction, calculate values, and re-update the smbo state
                # assumption: we only get one point tuple from smbo for each iteration
                info("> ExecStrategy   | mlrMBO artifacts created successfully", Fore.CYAN)
                iteration_index = 0
                successful_update = True
                info("optimizer_iterations | " + str(wf.execution_strategy["optimizer_iterations"]))
                while iteration_index < wf.execution_strategy["optimizer_iterations"]:
                    if successful_update is True:
                        proposed_points = get_proposed_points(wf)
                        if proposed_points:
                            for point in proposed_points:
                                exp = create_experiment_tuple(wf, point)
                                if objectives_number == 1:
                                    result = float(experimentFunction(wf, exp))
                                else:
                                    result = experimentFunction(wf, exp)
                                knobs_and_results.append((exp["knobs"], result))
                                successful_update = update_mbo_state(wf, point, result)
                        else:
                            err_msg = {"error": "Error occurred while running experimentFunction and getting new proposed points"}
                            error(err_msg)
                            return None
                    iteration_index += 1
                finalize_optimization(wf)
                return recreate_knob_from_optimizer_values(knobs_and_results)
            else:
                err_msg = {"error": res["result"]}
                error(err_msg)
                return None
        else:
            err_msg = {"error": "Cannot create artifacts, make sure R server is up and running"}
            error(err_msg)
            return None
    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


def update_mbo_state(wf, proposed_points, value):
    try:
        body = dict(
            id=wf.rtx_run_id,
            knobs=proposed_points,
            value=value
        )
        api = host_with_port + "/mlrMBO/model/update"
        r = requests.post(api, data=json.dumps(body), headers=header)
        res = r.json()
        if "result" in res:
            return True
        else:
            err_msg = {"error": "An error occurred in updating mlrMBO model, please restart the optimization"}
            error(err_msg)
            return False

    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


def get_proposed_points(wf):
    try:
        body = dict(
            id=wf.rtx_run_id
        )
        api = host_with_port + "/mlrMBO/model/getProposedPoint"
        r = requests.post(api, data=json.dumps(body), headers=header)
        res = r.json()
        if res:
            return res
        elif "result" in res:
            err_msg = {"error": res["result"]}
            error(err_msg)
            return None
        else:
            err_msg = {"error": "Unexpected error occurred while getting proposed points"}
            error(err_msg)
            return None
    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


def create_experiment_tuple(wf, knobs):
    exp = dict()
    exp["ignore_first_n_results"] = wf.execution_strategy["ignore_first_n_results"]
    exp["sample_size"] = wf.execution_strategy["sample_size"]
    exp["knobs"] = knobs
    return exp


def finalize_optimization(wf):
    try:
        body = dict(
            id=wf.rtx_run_id
        )
        api = host_with_port + "/mlrMBO/finalize"
        r = requests.post(api, data=json.dumps(body), headers=header)
        res = r.json()
        if "result" in res:
            if res["result"] is True:
                return "MLR strategy has ended"
            else:
                err_msg = {"error": res["result"]}
                error(err_msg)
                return None
        else:
            err_msg = {"error": "An error occurred in finalizing mlrMBO optimization"}
            error(err_msg)
            return None
    except requests.ConnectionError as e:
        error(connection_err_msg)
        return None


def recreate_knob_from_optimizer_values(knobs_and_results):
    """ recreates knob values from a variable
        independent of criteria for data type (minimization, maximization), we will get minimal result
        because it's already handled it in wf.evaluator """
    info("knobs_and_results | " + str(knobs_and_results))
    knobs_and_results = sorted(knobs_and_results, key=lambda x: x[1])
    info("sorted knobs_and_results | " + str(knobs_and_results))
    return knobs_and_results[0][0], knobs_and_results[0][1] # 0: knob_object, 1: value


def update_topics(wf):

    suffix = "-" + str(wf.seed)

    original_primary_data_provider_topic = wf.primary_data_provider["topic"]
    original_secondary_data_provider_topic = wf.secondary_data_providers[0]["topic"]
    original_change_provider_topic = wf.change_provider["topic"]

    wf.primary_data_provider["topic"] = original_primary_data_provider_topic + suffix
    wf.primary_data_provider["instance"].topic = original_primary_data_provider_topic + suffix
    wf.secondary_data_providers[0]["topic"] = original_secondary_data_provider_topic + suffix
    wf.secondary_data_providers[0]["instance"].topic = original_secondary_data_provider_topic + suffix
    wf.secondary_data_providers[0]["instance"].reset()
    wf.change_provider["topic"] = original_change_provider_topic + suffix
    wf.change_provider["instance"].topic = original_change_provider_topic + suffix

    info("Listening to " + wf.primary_data_provider["topic"])
    info("Listening to " + wf.secondary_data_providers[0]["topic"])
    info("Posting changes to " + wf.change_provider["topic"])