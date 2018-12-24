from time import sleep
import multiprocessing as mpc
import subprocess
import os,sys,signal
import argparse

# Set SUMO home
os.environ['SUMO_HOME'] = '/usr/share/sumo'
os.environ['CROWDNAV']  = '../CrowdNav'#'/home/erik/research/DARTS-TMP/CrowdNav'
os.environ['RTX']       = '.'#'/home/erik/research/DARTS-TMP/RTX'

sys.path.append(os.path.join(os.environ.get("SUMO_HOME"), "tools"))
sys.path.append('../CrowdNav')

# Import CrowdNav/RTX libs
from app import Boot
import imp
import json
import rtxlib
import random
from colorama import Fore
from rtxlib import info, error, debug
from rtxlib.workflow import execute_workflow
from rtxlib.report import plot
from rtxlib.databases import create_instance
from rtxlib.databases import get_no_database


# Handle arguments
parser = argparse.ArgumentParser(description='SEAMS2019 Experiment Controller.')
#parser.add_argument('--seed', help='Initializes random seed. Random seed if left blank.', type=int)
parser.add_argument('--experiment', help='Path to experiment folder.', default='examples/crowdnav-bayesian-multi-objective')
parser.add_argument('--num_replicates', help='Number of experimental replicates.', type=int, default=30)
#parser.add_argument('--processor_count', help='Number of processors to use.', type=int, default=4)

# CrowdNav
parser.add_argument('--process_id', help='Process ID to use.', type=int, default=0)
parser.add_argument('--gui', help='Use SUMO GUI.', action='store_true')


def rtx_load_definition(folder):
  """ opens the given folder and searches for a definition.py file and checks if it looks valid"""
  try:
    wf = imp.load_source('wf', './' + folder + '/definition.py')
    wf.folder = folder
    testName = wf.name
    return wf
  except IOError:
    error("Folder is not a valid experiment folder (does not contain definition.py)")
    exit(1)
  except AttributeError:
    error("Workflow did not had a name attribute")
    exit(1)
  except ImportError as e:
    error("Import failed: " + str(e))
    exit(1)

def crowdnav_process(seed):
  Boot.start(args.process_id, parallelMode, args.gui, seed)

def rtx_process(folder,seed):
  # Load experiment
  wf = rtx_load_definition(folder)
  if os.path.isfile('oeda_config.json'):
    with open('oeda_config.json') as json_data_file:
      try:
        config_data = json.load(json_data_file)
      except ValueError:
        # config.json is empty - default configuration used
        config_data = []
  else:
    config_data = []

    # check for database configuration
    if "database" in config_data:
      database_config = config_data["database"]
      info("> RTX configuration: Using " + database_config["type"] + " database.", Fore.CYAN)
      db = create_instance(database_config)
      wf.rtx_run_id = db.save_rtx_run(wf.execution_strategy)
      wf.db = db
    else:
      info("> RTX configuration: No database specified.", Fore.CYAN)
      wf.rtx_run_id = "-1"
      wf.db = get_no_database()

  # setting global variable log_folder for logging and clear log
  rtxlib.LOG_FOLDER = wf.folder
  rtxlib.clearOldLog()
  info("> Starting RTX experiment...")

  execute_workflow(wf)
  plot(wf)
#  exit(0)


if __name__ == '__main__':
  args = parser.parse_args()

  # Check for parallel mode
  parallelMode = False
  if args.process_id > 0:
    parallelMode = True

  # Loop for the required number of iterations
  for i in range(args.num_replicates):
    seed = i

    print "======================================================"
    print "REPLICATE [%d]" % i
    print "======================================================"


    """ Run CrowdNav """
    # Start application
    p1 = mpc.Process(target=crowdnav_process, args=(seed,))
    p1.daemon = True
    p1.start()
    sleep(10)

    """ Run RTX """
    p2 = mpc.Process(target=rtx_process, args=(args.experiment,seed,))
    p2.start()
    p2.join()
    sleep(10)

    p1.terminate()

 # if len(sys.argv) > 2 and sys.argv[1] == "report":
 #   wf = loadDefinition(sys.argv[2])
 #   info("> Starting RTX reporting...")
 #   plot(wf)
 #   exit(0)