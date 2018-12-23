from json import load
from rtxlib import error, info
from rtxlib.databases import create_instance
from colorama import Fore
import os.path
import pickle


class NonLocal: DB = None


RAW_DATA_FOLDER_NAME = "raw_data"


def setup_database(index_name=None):

    with open('oeda_config.json') as json_data_file:
        try:
            config_data = load(json_data_file)
        except ValueError:
            error("> You need to specify a database configuration in oeda_config.json.")
            exit(0)

    if "database" not in config_data:
        error("You need to specify a database configuration in oeda_config.json.")
        exit(0)

    database_config = config_data["database"]
    if index_name:
        database_config["index"]["name"] = index_name
    info("> OEDA configuration: Using " + database_config["type"] + " database.", Fore.CYAN)

    NonLocal.DB = create_instance(database_config)


def db():
        if not NonLocal.DB:
            error("You have to setup the database.")
            exit(0)
        return NonLocal.DB


def save_dict_to_file(data, path_to_file):
    pickle_out = open(path_to_file,"wb")
    pickle.dump(data, pickle_out)
    pickle_out.close()
    print "data saved to file " + path_to_file


def retrieve_dict_from_file(path_to_file):
    pickle_in = open(path_to_file,"rb")
    data = pickle.load(pickle_in)
    print "data retrieved from file " + path_to_file
    return data


def get_raw_data(index, refresh):
    file_name = index + ".pickle"
    path_to_file = os.path.join(RAW_DATA_FOLDER_NAME, file_name)
    if os.path.exists(path_to_file) and not refresh:
        res = retrieve_dict_from_file(path_to_file)
    else:
        setup_database(index)
        res = db().get_all_data_points()
        save_dict_to_file(res, path_to_file)
    return res
