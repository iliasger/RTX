# Abstract interface for a database
#
# A database stores the raw data and the experiment runs of RTX.


class Database:

    def __init__(self):
        pass

    def save_rtx_run(self, strategy):
        """ saves the parameters of an rtx run and returns the auto-generated id """
        pass

    def update_rtx_run(self, rtx_run_id, exp_count, list_of_configurations):
        """ updates the experiment count and the list of configurations parameters of the rtx run with the given id """
        pass

    def get_exp_count(self, rtx_run_id):
        """ returns the experiment count parameter of the rtx run specified by its id """
        pass

    def get_list_of_configurations(self, rtx_run_id):
        """ returns the list of configurations parameter of the rtx run specified by its id """
        pass

    def get_sample_size(self, rtx_run_id):
        """ returns the streategy's sample size of the rtx run specified by its id """
        pass

    def save_data_point(self, exp_run, knobs, payload, data_point_id, rtx_run_id):
        """ called for saving experiment configuration runs and raw data """
        pass

    def get_data_points(self, rtx_run_id, exp_run):
        """ called for getting all the data points corresponding to an analytis run """
        pass

    def save_analysis(self, rtx_run_ids, name, result):
        """ saves the parameters and the result of an analysis """
        pass