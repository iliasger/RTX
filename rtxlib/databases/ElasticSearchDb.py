import traceback

from rtxlib.databases.Database import Database
from elasticsearch import Elasticsearch
from elasticsearch.client import IndicesClient
from elasticsearch.exceptions import TransportError
from elasticsearch.exceptions import ConnectionError
from datetime import datetime
from rtxlib import error
from elasticsearch.helpers import scan

class ElasticSearchDb(Database):

    def __init__(self, db_config):
        self.es = Elasticsearch([{"host": db_config["host"], "port": db_config["port"]}])

        if not self.es.ping():
            error("cannot connect to elasticsearch cluster. Check database configuration in config.json.")
            exit(0)

        index = db_config["index"]
        self.index = index["name"]
        rtx_run_type = db_config["rtx_run_type"]
        self.rtx_run_type_name = rtx_run_type["name"]
        analysis_type = db_config["analysis_type"]
        self.analysis_type_name = analysis_type["name"]
        data_point_type = db_config["data_point_type"]
        self.data_point_type_name = data_point_type["name"]
        target_system_type = db_config["target_system_type"]
        self.target_system_type_name = target_system_type["name"]

        mappings = dict()
        # user can specify an type without a mapping (dynamic mapping)
        if "mapping" in rtx_run_type:
            mappings[self.rtx_run_type_name] = rtx_run_type["mapping"]
        if "mapping" in analysis_type:
            mappings[self.analysis_type_name] = analysis_type["mapping"]
        if "mapping" in data_point_type:
            mappings[self.data_point_type_name] = data_point_type["mapping"]

        body = dict()
        if "settings" in index:
            body["settings"] = index["settings"]
        if mappings:
            body["mappings"] = mappings

        try:
            self.indices_client = IndicesClient(self.es)
            if not self.indices_client.exists(self.index):
                self.indices_client.create(self.index, body)
        except TransportError:
            error("Error while creating elasticsearch. Check type mappings in oeda_config.json.")
            print(traceback.format_exc())
            exit(0)

    def save_target_system(self, target_system_id, primary_data_provider, change_provider):
        body = dict()
        body["primary_data_provider"] = primary_data_provider
        body["change_provider"] = change_provider
        body["in_use"] = False
        body["created"] = datetime.now()
        try:
            self.es.index(self.index, self.target_system_type_name, body, target_system_id)
        except ConnectionError:
            error("Error while saving rtx_run data in elasticsearch. Check connection to elasticsearch and restart.")
            exit(0)

    def use_target_system(self, target_system_id):
        self.set_target_system_in_use(target_system_id)
        return self.get_target_system_info(target_system_id)

    def release_target_system(self, target_system_id):
        self.toggle_target_system_in_use(target_system_id, False)

    def set_target_system_in_use(self, target_system_id):
        self.toggle_target_system_in_use(target_system_id, True)

    def get_target_system_info(self, target_system_id):
        res = self.es.get(self.index, target_system_id, self.target_system_type_name,
                          _source=["primary_data_provider", "change_provider"])
        source = res["_source"]
        if "primary_data_provider" not in source:
            error("'primary_data_provider' does not exist in target system with id " + target_system_id)
            return None, None
        if "change_provider" not in source:
            error("'change_provider' does not exist in target system with id " + target_system_id)
            return None, None
        return source["primary_data_provider"], source["change_provider"]

    def toggle_target_system_in_use(self, target_system_id, in_use):
        body = {"doc": {"in_use": in_use}}
        try:
            self.es.update(self.index, self.target_system_type_name, target_system_id, body)
        except ConnectionError:
            error("Error while updating target system in_use flag in elasticsearch. Check connection to elasticsearch.")

    def save_rtx_run(self, strategy, seed):
        body = dict()
        body["strategy"] = strategy
        body["created"] = datetime.now()
        body["seed"] = seed
        try:
            res = self.es.index(self.index, self.rtx_run_type_name, body)
            return res['_id']
        except ConnectionError:
            error("Error while saving rtx_run data in elasticsearch. Check connection to elasticsearch and restart.")
            exit(0)

    def get_exp_count(self, rtx_run_id):
        res = self.es.get(self.index, rtx_run_id, self.rtx_run_type_name, _source=["strategy"])
        if "exp_count" not  in res["_source"]["strategy"]:
            error("'exp_count' does not exist in rtx run' strategy with id " + rtx_run_id)
            return 0
        return res["_source"]["strategy"]["exp_count"]

    def save_data_point(self, exp_run, knobs, payload, data_point_count, rtx_run_id, output, processor_id=0):
        data_point_id = rtx_run_id + "#It_" + str(exp_run) + "#Ind_" + str(processor_id) + "#No_" + str(data_point_count) + "#out_" + output
        body = dict()
        body["exp_run"] = exp_run
        body["knobs"] = knobs
        body["payload"] = payload
        body["created"] = datetime.now()
        try:
            self.es.index(self.index, self.data_point_type_name, body, data_point_id, parent=rtx_run_id)
        except ConnectionError:
            error("Error while saving data point data in elasticsearch. Check connection to elasticsearch.")


    def save_data_for_experiment(self, exp_run, knobs, payload, rtx_run_id, processor_id=0):
        data_point_id = rtx_run_id + "#It_" + str(exp_run) + "#Ind_" + str(processor_id)
        body = dict()
        body["iteration"] = exp_run
        body["individual"] = processor_id
        body["knobs"] = knobs
        body["payload"] = payload
        body["created"] = datetime.now()
        try:
            self.es.index(self.index, self.data_point_type_name, body, data_point_id, parent=rtx_run_id)
        except ConnectionError:
            error("Error while saving data point data in elasticsearch. Check connection to elasticsearch.")

    # Insert performance metrics into database - postprocessed
    # %proc, RAM (kb), %E, %S, %U
    def insert_metrics(self, run_id, metrics, seed, experiment_name):
      body = dict()
      body["processor_usage"] = metrics[0]
      body["ram_usage_kb"]    = metrics[1]
      body["real_time"]       = metrics[2]
      body["system_time"]     = metrics[3]
      body["user_time"]       = metrics[4]
      body["seed"]            = seed
      body["experiment_name"] = experiment_name

      name = "performance_metrics_" + experiment_name + "_" + seed

      try:
        self.es.index(run_id, self.data_point_type_name, body, name, parent=run_id)
      except ConnectionError:
        error("Error while saving performance metrics in elasticsearch. Check connection to elasticsearch.")

    def get_data_points(self, rtx_run_id, exp_run):
        query = {
            "query": {
                "parent_id" : {
                    "type": "data_point",
                    "id" : str(rtx_run_id)
                }
            },
            "post_filter": {
                "term": { "exp_run": int(exp_run) }
            }
        }
        self.indices_client.refresh()
        res = self.es.search(self.index, self.data_point_type_name, query)
        return [(data["_source"]["payload"], data["_source"]["knobs"]) for data in res["hits"]["hits"]]

    def save_analysis(self, rtx_run_ids, name, result):
        ids_str = reduce(lambda a,b: a+"+"+b, rtx_run_ids[1:], rtx_run_ids[0])
        analysis_id = ids_str + "_" + name
        body = dict()
        body["rtx_run_ids"] = rtx_run_ids
        body["name"] = name
        body["result"] = result
        body["created"] = datetime.now()
        try:
            self.es.index(self.index, self.analysis_type_name, body, analysis_id)
        except ConnectionError:
            error("Error while saving analysis data in elasticsearch. Check connection to elasticsearch.")

    def get_all_data_points(self):
        self.indices_client.refresh()

        rtx_runs = list()
        data = list()
        performance_data = list()

        for doc in scan(self.es,
                        query={"query": {"match_all": {}}},
                        index=self.index,
                        doc_type=self.rtx_run_type_name):
            res = dict()
            res["id"] = doc["_id"]
            res["strategy"] = doc["_source"]["strategy"]
            res["time"] = doc["_source"]["created"]
            res["seed"] = doc["_source"]["seed"]
            rtx_runs.append(res)

        for doc in scan(self.es,
                        query={"query": {"match_all": {}}},
                        index=self.index,
                        doc_type=self.data_point_type_name):
            res = dict()
            res["parent"] = doc["_parent"]
            res["_source"] = doc["_source"]

            if "seed" in doc["_source"]:
                performance_data.append(res)
            else:
                data.append(res)

        return rtx_runs, data, performance_data
