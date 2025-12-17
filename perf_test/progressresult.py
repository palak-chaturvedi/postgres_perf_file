import json
from DatabaseOperations import DatabaseOperations

class progressresult:
    def __init__(self):
        self.experiment_id = None
        self.target_server_id = None
        self.report_interval = None
        self.transactions = 0
        self.tps = 0.0
        self.qps = 0.0
        self.reconnects = 0
        self.total_time_s = 0.0
        self.latency_min_ms = 0.0
        self.latency_avg_ms = 0.0
        self.latency_max_ms = 0.0
        self.latency_percentile_95_ms = 0.0
        self.latency_percentile_90_ms = 0.0
        self.latency_percentile_80_ms = 0.0
        self.latency_percentile_50_ms = 0.0
        self.latency_percentile_sum_ms = 0.0
        self.run_type = None
        self.db_type = "Postgres"
        self.progress_reports = []
        self.statement_latencies_lines = []
        self.starttime=""
        self.endtime=""
        self.scaling_factor=""
        self.query_mode=""
        self.num_transactionsperclient=0
        self.num_transactionsprocessed=""
        self.duration_in_s=0
        self.latency_stdev_ms=0
        self.querymode=""
        self.kusto_string=""
        self.results_string=""
        self.kustofilepath=""
        self.ssh_key_path=""
        dbinittime=""

    