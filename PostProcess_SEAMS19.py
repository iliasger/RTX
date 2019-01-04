# This file reads in an output file by running:
# (/usr/bin/time -f '%P %M %E %S %U' python rtx.py <example>) &> rtx_experiment.output
# This will output all RTX data into the .output file, including the performance metrics in the format:
# PROCESSOR (%), RAM (KB), ELAPSED (time), SYSTEM (time), USER (time)

# At present, this file assumes that an elastic instance exists. 
import os, sys, elasticsearch, json

from rtxlib.databases import create_instance
from rtxlib.databases import get_no_database

assert(len(sys.argv) == 4), "Required arguments: *.output file and seed!"
assert(os.path.isfile(sys.argv[1])), "File [%s] not found!" % sys.argv[1]
assert(os.path.isfile('oeda_config.json')), 'Database config file not found!'

# .output file required
with open(sys.argv[1]) as f:
  lines = f.readlines()

  # %proc, RAM (kb), %E, %S, %U
  performance_metrics = lines[-1].split()
  print performance_metrics

  # Create database instance
  config_data = []
  with open('oeda_config.json') as json_data_file:
    try:
      config_data = json.load(json_data_file)
    except ValueError:
      # config.json is empty - default configuration used
      config_data = []

  # check for database configuration
  if "database" in config_data:
    database_config = config_data["database"]
    print("> [Postprocess] RTX configuration: Using " + database_config["type"] + " database.")
    db = create_instance(database_config)
    db.insert_metrics(database_config["index"]["name"], performance_metrics, sys.argv[2], sys.argv[3])
  else:
    print("Database error.")
