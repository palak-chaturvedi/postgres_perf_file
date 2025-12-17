import json
import csv
import os
from datetime import datetime
import platform
import threading
import time
import logging

try:
    import psutil
except ImportError:
    print("WARNING: psutil not installed. System monitoring will be disabled.")
    psutil = None

try:
    import psycopg2
except ImportError:
    print("WARNING: psycopg2 not installed. Database upload will be disabled.")
    psycopg2 = None

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


class DatabaseOperations:
    """Helper class for database operations"""
    
    @staticmethod
    def connectresultdb(hosturl, dbport, username, password, dbname):
        """Connect to Azure PostgreSQL database"""
        try:
            connection = psycopg2.connect(
                host=hosturl,
                port=dbport,
                user=username,
                password=password,
                database=dbname,
                sslmode='require',
                connect_timeout=10
            )
            logger.info(f"Successfully connected to database {dbname} at {hosturl}")
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None


class StatementLatency:
    """Simple class to hold statement latency information"""
    def __init__(self, latency_ms, statement):
        self.latency_ms = latency_ms
        self.statement = statement


class PopulateResult:
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
        self.db_type = "og_postgres"
        self.progress_reports = []
        self.statement_latencies_lines = []
        self.starttime = ""
        self.endtime = ""
        self.scaling_factor = ""
        self.query_mode = ""
        self.num_transactionsperclient = 0
        self.num_transactionsprocessed = ""
        self.duration_in_s = 0
        self.latency_stdev_ms = 0
        self.querymode = ""
        self.kusto_string = ""
        self.results_string = ""
        self.warmupresults_string = ""
        self.kustofilepath = ""
        self.ssh_key_path = ""
        self.resultdbhosturl = ""
        self.resultdbdbport = ""
        self.resultdbusername = ""
        self.resultdbpassword = ""
        self.resultdbdbname = ""
        # self.dbinitstarttime=""
        # self.dbinitendtime=""
        # self.warmuprunstarttime=""
        # self.warmuprunendtime=""
        # self.measurementrunstarttime=""
        # self.measurementrunendtime=""
        self.dbinitstarttime = ""
        self.dbinitendtime = ""
        self.teststarttime = ""
        self.testendtime = ""
        self.testname = ""
        self.testtype = ""
        self.pgcommand = ""
        self.warmupfilepath = ""
        self.client_name = platform.uname()[1]
        self.tps_including_connection_establishing = 0.0
        self.tps_excluding_connection_establishing = 0.0
        
        # Initialize missing attributes that are expected by parsing logic
        self.transaction_type = ""
        self.num_clients = 0
        self.num_threads = 0
        self.latency_average_ms = 0.0
        self.tps_without_initial_connection_time = 0.0
        
        # System monitoring attributes
        self.cpu_usage_percent = 0.0
        self.memory_usage_percent = 0.0
        self.memory_used_mb = 0.0
        self.memory_available_mb = 0.0
        self.disk_io_read_mb = 0.0
        self.disk_io_write_mb = 0.0
        self.network_io_sent_mb = 0.0
        self.network_io_recv_mb = 0.0
        self.load_average_1min = 0.0
        self.postgres_cpu_percent = 0.0
        self.postgres_memory_mb = 0.0
        
        # System monitoring control
        self.monitoring_active = False
        self.monitoring_thread = None
        self.monitoring_data = []
        self.statement_latencies = []

    def start_monitoring(self):
        """Start system monitoring in a separate thread"""
        if psutil is None:
            print("WARNING: psutil not available, system monitoring disabled")
            return
            
        print("Starting system monitoring")
        self.monitoring_active = True
        self.monitoring_data = []
        self.monitoring_thread = threading.Thread(target=self._monitor_system)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

    def stop_monitoring(self):
        """Stop system monitoring and calculate averages"""
        if not self.monitoring_active or psutil is None:
            return
            
        print("Stopping system monitoring")
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Calculate averages from collected data
        if self.monitoring_data:
            self._calculate_monitoring_averages()
        else:
            print("Warning: No monitoring data collected")

    def _monitor_system(self):
        """Internal method to collect system metrics"""
        postgres_processes = []
        
        # Find PostgreSQL processes
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'postgres' in proc.info['name'].lower():
                        postgres_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Warning: Error finding postgres processes: {e}")
        
        if len(postgres_processes) > 0:
            print(f"Monitoring {len(postgres_processes)} PostgreSQL processes")
        
        while self.monitoring_active:
            try:
                # System-wide metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                net_io = psutil.net_io_counters()
                
                # Load average (Unix-like systems only)
                load_avg = 0.0
                try:
                    load_avg = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
                except:
                    pass
                
                # PostgreSQL-specific metrics
                postgres_cpu = 0.0
                postgres_memory = 0.0
                
                for proc in postgres_processes[:]:  # Use slice to avoid modification during iteration
                    try:
                        postgres_cpu += proc.cpu_percent()
                        postgres_memory += proc.memory_info().rss / 1024 / 1024  # Convert to MB
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        postgres_processes.remove(proc)  # Process no longer exists
                    except Exception as e:
                        pass  # Skip process that can't be accessed
                
                # Store monitoring data point
                data_point = {
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_mb': memory.used / 1024 / 1024,
                    'memory_available_mb': memory.available / 1024 / 1024,
                    'disk_io_read_mb': disk_io.read_bytes / 1024 / 1024 if disk_io else 0,
                    'disk_io_write_mb': disk_io.write_bytes / 1024 / 1024 if disk_io else 0,
                    'network_io_sent_mb': net_io.bytes_sent / 1024 / 1024 if net_io else 0,
                    'network_io_recv_mb': net_io.bytes_recv / 1024 / 1024 if net_io else 0,
                    'load_average_1min': load_avg,
                    'postgres_cpu_percent': postgres_cpu,
                    'postgres_memory_mb': postgres_memory
                }
                
                self.monitoring_data.append(data_point)
                
                time.sleep(1)  # Collect data every second
                
            except Exception as e:
                time.sleep(1)  # Continue monitoring even if there's an error

    def _calculate_monitoring_averages(self):
        """Calculate average values from collected monitoring data"""
        if not self.monitoring_data:
            return
            
        print(f"Calculating system monitoring averages from {len(self.monitoring_data)} data points")
        
        # Calculate averages
        self.cpu_usage_percent = sum(d['cpu_percent'] for d in self.monitoring_data) / len(self.monitoring_data)
        self.memory_usage_percent = sum(d['memory_percent'] for d in self.monitoring_data) / len(self.monitoring_data)
        self.memory_used_mb = sum(d['memory_used_mb'] for d in self.monitoring_data) / len(self.monitoring_data)
        self.memory_available_mb = sum(d['memory_available_mb'] for d in self.monitoring_data) / len(self.monitoring_data)
        
        # For I/O metrics, use the difference between first and last readings
        if len(self.monitoring_data) > 1:
            first = self.monitoring_data[0]
            last = self.monitoring_data[-1]
            duration = last['timestamp'] - first['timestamp']
            
            if duration > 0:
                self.disk_io_read_mb = (last['disk_io_read_mb'] - first['disk_io_read_mb']) / duration
                self.disk_io_write_mb = (last['disk_io_write_mb'] - first['disk_io_write_mb']) / duration
                self.network_io_sent_mb = (last['network_io_sent_mb'] - first['network_io_sent_mb']) / duration
                self.network_io_recv_mb = (last['network_io_recv_mb'] - first['network_io_recv_mb']) / duration
        
        self.load_average_1min = sum(d['load_average_1min'] for d in self.monitoring_data) / len(self.monitoring_data)
        self.postgres_cpu_percent = sum(d['postgres_cpu_percent'] for d in self.monitoring_data) / len(self.monitoring_data)
        self.postgres_memory_mb = sum(d['postgres_memory_mb'] for d in self.monitoring_data) / len(self.monitoring_data)
        
        print(f"System monitoring summary - CPU: {self.cpu_usage_percent:.1f}%, Memory: {self.memory_usage_percent:.1f}%, PostgreSQL CPU: {self.postgres_cpu_percent:.1f}%, PostgreSQL Memory: {self.postgres_memory_mb:.1f}MB")

    @classmethod
    def load_result_in_db(cls, result_config, targetserver, pgcommand, testname, warmup, monitoring_result=None):
        print(f"Processing results for {testname} ({'warmup' if warmup == 'true' else 'measurement'} run)")
        
        pgresult = PopulateResult()
        
        # Copy monitoring data if provided
        if monitoring_result and warmup == "false":  # Only for measurement runs
            print("Collecting system monitoring data")
            pgresult.cpu_usage_percent = getattr(monitoring_result, 'cpu_usage_percent', 0.0)
            pgresult.memory_usage_percent = getattr(monitoring_result, 'memory_usage_percent', 0.0)
            pgresult.memory_used_mb = getattr(monitoring_result, 'memory_used_mb', 0.0)
            pgresult.memory_available_mb = getattr(monitoring_result, 'memory_available_mb', 0.0)
            pgresult.disk_io_read_mb = getattr(monitoring_result, 'disk_io_read_mb', 0.0)
            pgresult.disk_io_write_mb = getattr(monitoring_result, 'disk_io_write_mb', 0.0)
            pgresult.network_io_sent_mb = getattr(monitoring_result, 'network_io_sent_mb', 0.0)
            pgresult.network_io_recv_mb = getattr(monitoring_result, 'network_io_recv_mb', 0.0)
            pgresult.load_average_1min = getattr(monitoring_result, 'load_average_1min', 0.0)
            pgresult.postgres_cpu_percent = getattr(monitoring_result, 'postgres_cpu_percent', 0.0)
            pgresult.postgres_memory_mb = getattr(monitoring_result, 'postgres_memory_mb', 0.0)
        pgresult.target_server_id = targetserver["pgserver_hosturl"]
        
        # Set database configuration
        pgresult.resultdbhosturl = "orcas-perf-dojo-results-db.postgres.database.azure.com"
        pgresult.resultdbdbport = "5432"
        pgresult.resultdbusername = "meruperfadmin@orcas-perf-dojo-results-db"
        pgresult.resultdbpassword = "password@123"
        pgresult.resultdbdbname = "merupgperf"
        
        # Use simple file paths instead of JSON config
        if warmup == "true":
            summaryfilepath = "warmup_output_file_path.txt"
        else:
            summaryfilepath = "summary_output_file_path.txt"
        
        pgresult.warmupfilepath = "warmup_output_file_path.txt"
        progressfilepath = "progress_output_file_path.txt"
        
        pgresult.testname = testname
        pgresult.pgcommand = pgcommand
        pgresult.testtype = "measurement"
        if warmup == "true":
            pgresult.testtype = "WarmUp"
        
        print(f"Parsing benchmark results for {testname}")
        cls.results(pgresult, summaryfilepath, targetserver, progressfilepath, warmup)

    @classmethod
    def results(cls, pgresult, summaryfilepath, targetserver, progressfilepath, warmup):
        try:
            num_lines_in_summary_file = 0
            num_lines_in_progress_file = 0
            
            # Check if files exist
            if not os.path.exists(summaryfilepath):
                print(f"WARNING: Summary file {summaryfilepath} not found")
                return
                
            if not os.path.exists(progressfilepath):
                print(f"WARNING: Progress file {progressfilepath} not found")
                return
            
            with open(summaryfilepath, 'r') as summary_file:
                for line in summary_file:
                    num_lines_in_summary_file += 1
                    
            with open(progressfilepath, 'r') as progress_file:
                for line in progress_file:
                    num_lines_in_progress_file += 1
            
            cls.parse_summary_file(pgresult, summaryfilepath, targetserver, progressfilepath, warmup)

        except Exception as err:
            print(f"ERROR: Failed to display result files: {err}")

    @classmethod
    def parse_summary_file(cls, pgresult, summaryfilepath, targetserver, progressfilepath, warmup):
        ''' Reads the summary file and populates the result's fields.

        :param result: an instance of PGBenchResult
        :param summary_file_path:  path to the summary file
        :return: None, raises an exception if anything goes wrong
        '''

        
        if(warmup == "false"):
            if("RO_" in pgresult.testname or "RW_" in pgresult.testname):
                try:
                    with open(pgresult.warmupfilepath, 'r') as in_file2:
                        lines2 = [line2 for line2 in in_file2]
                    for line_num, line2 in enumerate(lines2):
                        pgresult.results_string += line2
                except Exception as e:
                    print(f"Exception as follows: {e}")

        with open(summaryfilepath, 'r') as in_file:
            lines = [line for line in in_file]
        
        # TODO: this could be faster, but this seems more robust.
        for line_num, line in enumerate(lines):
            if "transaction type" in line:
                # transaction type: <builtin: TPC-B (sort of)>
                pgresult.transaction_type = line.split("type:")[1].strip()

            elif "scaling factor" in line:
                # scaling factor: 1
                pgresult.scaling_factor = int(line.split(":")[1].strip())

            elif "query mode" in line:
                # query mode: simple
                pgresult.query_mode = line.split(":")[1].strip()

            elif "number of clients" in line:
                # number of clients: 10
                pgresult.num_clients = int(line.split(":")[1].strip())

            elif "number of threads" in line:
                # number of threads: 10
                pgresult.num_threads = int(line.split(":")[1].strip())

            elif "duration" in line:
                # duration: 10 s
                pgresult.duration_in_s = line.split(":")[1].strip()

            elif "number of transactions per client" in line:
                # number of transactions actually processed: 148
                # number of transactions actually processed: 100/100
                pgresult.num_transactionsperclient = int(line.split(":")[1].strip().split("/")[0])
            elif "number of transactions actually processed" in line:
                # number of transactions actually processed: 148
                # number of transactions actually processed: 100/100
                pgresult.num_transactionsprocessed = int(line.split(":")[1].strip().split("/")[0])

            elif "latency average" in line:
                # latency average = 30.395 ms
                pgresult.latency_average_ms = float(line.split()[-2])

            elif "latency stddev" in line:
                # latency stddev = 9.599 ms
                pgresult.latency_stdev_ms = float(line.split()[-2])

            elif "including connections establishing" in line:
                # tps = 14.148400 (including connections establishing)
                pgresult.tps_including_connection_establishing = float(line.split()[2])

            elif "excluding connections establishing" in line:
                # tps = 235.683458 (excluding connections establishing)
                pgresult.tps_excluding_connection_establishing = float(line.split()[2])

            elif "script statistics" in line:
                pgresult.statement_latencies_lines = lines[line_num + 2:]
                break
            elif "DBInit StartTime" in line:
                # latency average = 30.395 ms
                pgresult.dbinitstarttime = line.split("=")[1].strip()
            elif "DBInit EndTime" in line:
                # latency average = 30.395 ms
                pgresult.dbinitendtime = line.split("=")[1].strip()
            elif "StartTime" in line:
                # latency average = 30.395 ms
                pgresult.teststarttime = line.split("=")[1].strip()
            elif "EndTime" in line:
                # latency average = 30.395 ms
                pgresult.testendtime = line.split("=")[1].strip()
            # For pgbench version >= 14
            elif "without initial connection time" in line:
                pgresult.tps_without_initial_connection_time = float(line.split()[2])

            pgresult.results_string += line
        for line in pgresult.statement_latencies_lines:
            latency_ms = float(line[:14].strip())
            statement = line[16:].strip()
            pgresult.statement_latencies.append(StatementLatency(latency_ms, statement))

        # with open(kustofilepath, 'r') as in_file1:
        #     lines1 = [line1 for line1 in in_file1]
        pgresult.kusto_string = ""
        # TODO: this could be faster, but this seems more robust.
        servertype=""
        if ("flexserver" in pgresult.target_server_id):
            # print(pgresult.target_server_id)
            servertype = "fspg"
            # for line_num, line1 in enumerate(lines1):
            #     if "let ServerName = SERVERNAME;" in line1:
            split_hostname = str(pgresult.target_server_id.split(".")[0])
            pgresult.kusto_string += "let ServerName = \"" + str(split_hostname) + "\";\n"
                # elif "let StartTime = datetime(STARTTIME);" in line1:
            pgresult.kusto_string += "let StartTime = datetime(" + str(pgresult.dbinitstarttime) + ");\n"
                # elif "let EndTime = datetime(ENDTIME);" in line1:
            pgresult.kusto_string += "let EndTime = datetime(" + str(pgresult.testendtime) + "); \n"
                # elif "| extend SandboxUpTimeInMin = datetime_diff('minute', max_originalEventTimestamp, min_originalEventTimestamp)" in line1:
                #     pgresult.kusto_string += "| extend SandboxUpTimeInMin = datetime_diff(''minute'', max_originalEventTimestamp, min_originalEventTimestamp)\n"
                # else:
                #     pgresult.kusto_string += line1

        logger.info(f"Completed {pgresult.testname} {pgresult.testtype} run for {pgresult.duration_in_s} seconds on {pgresult.target_server_id}")
        
        # The format of pgbench output has changed from version 14 onwards. 
        # This if condition allows the right value of tps to be reported.
        tps = 0.0
        if "pgbench_version" in targetserver and targetserver["pgbench_version"] < 14:
            tps = pgresult.tps_including_connection_establishing
        else:
            tps = getattr(pgresult, 'tps_without_initial_connection_time', pgresult.tps_including_connection_establishing)
        
        # Upload results to database
        if psycopg2 and pgresult.resultdbhosturl:
            try:
                connection = DatabaseOperations.connectresultdb(
                    pgresult.resultdbhosturl, 
                    pgresult.resultdbdbport, 
                    pgresult.resultdbusername, 
                    pgresult.resultdbpassword, 
                    pgresult.resultdbdbname
                )
                if connection is not None:
                    connection.autocommit = True
                    cursor = connection.cursor()
                    
                    try:
                        # Prepare data with proper NULL handling for integer fields
                        def safe_int(value):
                            """Convert value to int, return None for empty/invalid values"""
                            if value == "" or value is None:
                                return None
                            try:
                                return int(value)
                            except (ValueError, TypeError):
                                return None
                        
                        def safe_float(value):
                            """Convert value to float, return None for empty/invalid values"""
                            if value == "" or value is None:
                                return None
                            try:
                                return float(value)
                            except (ValueError, TypeError):
                                return None
                        
                        def safe_str(value):
                            """Convert value to string, return None for None values"""
                            if value is None:
                                return None
                            return str(value)
                        
                        # Use parameterized query to prevent SQL injection and handle NULLs properly
                        insert_query = """
                            INSERT INTO public.perfresults(
                                testname, starttime, endtime, scalingfactor, querymode, 
                                numberofclients, numberofthreads, numberoftpc, numberoftpp, 
                                latencyaverage, latencystddev, tpsincludingc, tpsexcludingc,
                                serverid, clientid, results, kustoqueries, 
                                dbinitstarttime, dbinitendtime, test_type, 
                                pgbench_command, servertype
                            ) VALUES (
                                %s, %s, %s, %s, %s, 
                                %s, %s, %s, %s, 
                                %s, %s, %s, %s,
                                %s, %s, %s, %s, 
                                %s, %s, %s, 
                                %s, %s
                            ) RETURNING "Experiment_ID"
                        """
                        
                        values = (
                            safe_str(pgresult.testname),
                            safe_str(pgresult.teststarttime) if pgresult.teststarttime else None,
                            safe_str(pgresult.testendtime) if pgresult.testendtime else None,
                            safe_int(pgresult.scaling_factor),
                            safe_str(pgresult.query_mode),
                            safe_int(pgresult.num_clients),
                            safe_int(pgresult.num_threads),
                            safe_int(pgresult.num_transactionsperclient),
                            safe_int(pgresult.num_transactionsprocessed),
                            safe_float(pgresult.latency_average_ms),
                            safe_float(pgresult.latency_stdev_ms),
                            safe_float(tps),
                            safe_float(pgresult.tps_excluding_connection_establishing),
                            safe_str(pgresult.target_server_id),
                            safe_str(pgresult.client_name),
                            safe_str(pgresult.results_string),
                            safe_str(pgresult.kusto_string),
                            safe_str(pgresult.dbinitstarttime) if pgresult.dbinitstarttime else None,
                            safe_str(pgresult.dbinitendtime) if pgresult.dbinitendtime else None,
                            safe_str(pgresult.testtype),
                            safe_str(pgresult.pgcommand),
                            safe_str(servertype) if servertype else None
                        )
                        
                        cursor.execute(insert_query, values)
                        experiment_id = cursor.fetchone()[0]
                        logger.info(f"Successfully uploaded results to database. Experiment ID: {experiment_id}")
                        
                        cursor.close()
                        connection.close()
                    except Exception as e:
                        logger.error(f"Failed to insert data into database: {e}", exc_info=True)
                        if connection:
                            connection.close()
            except Exception as e:
                logger.error(f"Failed to connect to the database: {e}", exc_info=True)
        else:
            if not psycopg2:
                logger.warning("psycopg2 not available, skipping database upload")
            elif not pgresult.resultdbhosturl:
                logger.info("Database configuration not provided, skipping database upload")
        
        # Write results to CSV file
        try:

            # Generate experiment ID (timestamp-based)
            experiment_id = int(datetime.now().timestamp() * 1000)  # milliseconds since epoch
            
            # CSV file path
            csv_filename = f"performance_results_{experiment_id}.csv"
            
            # Check if CSV file exists to determine if we need to write headers
            write_headers = not os.path.exists(csv_filename)
            
            # Prepare row data
            row_data = {
                'experiment_id': experiment_id,
                'testname': pgresult.testname,
                'test_type': pgresult.testtype,
                'starttime': pgresult.teststarttime,
                'endtime': pgresult.testendtime,
                'scalingfactor': pgresult.scaling_factor,
                'querymode': pgresult.query_mode,
                'numberofclients': pgresult.num_clients,
                'numberofthreads': pgresult.num_threads,
                'numberoftpc': pgresult.num_transactionsperclient,
                'numberoftpp': pgresult.num_transactionsprocessed,
                'latencyaverage': pgresult.latency_average_ms,
                'latencystddev': pgresult.latency_stdev_ms,
                'tpsincludingc': tps,
                'tpsexcludingc': pgresult.tps_excluding_connection_establishing,
                'serverid': pgresult.target_server_id,
                'clientid': pgresult.client_name,
                'dbinitstarttime': pgresult.dbinitstarttime,
                'dbinitendtime': pgresult.dbinitendtime,
                'pgbench_command': pgresult.pgcommand,
                'duration_seconds': pgresult.duration_in_s,
                'timestamp': datetime.now().isoformat(),
                # System monitoring metrics
                'cpu_usage_percent': round(getattr(pgresult, 'cpu_usage_percent', 0.0), 2),
                'memory_usage_percent': round(getattr(pgresult, 'memory_usage_percent', 0.0), 2),
                'memory_used_mb': round(getattr(pgresult, 'memory_used_mb', 0.0), 2),
                'memory_available_mb': round(getattr(pgresult, 'memory_available_mb', 0.0), 2),
                'disk_io_read_mb_per_sec': round(getattr(pgresult, 'disk_io_read_mb', 0.0), 4),
                'disk_io_write_mb_per_sec': round(getattr(pgresult, 'disk_io_write_mb', 0.0), 4),
                'network_io_sent_mb_per_sec': round(getattr(pgresult, 'network_io_sent_mb', 0.0), 4),
                'network_io_recv_mb_per_sec': round(getattr(pgresult, 'network_io_recv_mb', 0.0), 4),
                'load_average_1min': round(getattr(pgresult, 'load_average_1min', 0.0), 2),
                'postgres_cpu_percent': round(getattr(pgresult, 'postgres_cpu_percent', 0.0), 2),
                'postgres_memory_mb': round(getattr(pgresult, 'postgres_memory_mb', 0.0), 2)
            }
            
            # Write to CSV
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = list(row_data.keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if write_headers:
                    writer.writeheader()
                    print(f"Created new CSV file: {csv_filename}")
                
                writer.writerow(row_data)
                print(f"Successfully wrote {pgresult.testname} {pgresult.testtype} results to {csv_filename}")
                
        except Exception as e:
            print(f"ERROR: Failed to write results to CSV: {e}")
            
        print(f"Results Summary - {pgresult.testname} ({pgresult.testtype}):")
        print(f"  TPS: {tps:.2f}, Latency: {pgresult.latency_average_ms:.2f}ms, Clients: {pgresult.num_clients}, Threads: {pgresult.num_threads}")
        if warmup == "false":  # Only show system metrics for measurement runs
            print(f"  System - CPU: {pgresult.cpu_usage_percent:.1f}%, Memory: {pgresult.memory_usage_percent:.1f}%, PG Memory: {pgresult.postgres_memory_mb:.1f}MB")
          

