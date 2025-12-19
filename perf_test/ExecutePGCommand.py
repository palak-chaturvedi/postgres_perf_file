import os
import sys
import subprocess
import datetime
import re
import time
from PopulateResult import PopulateResult

class ExecutePGCommand():
    """
    It will Execute the PG commands against the Server and create Summary and Progress File

    """

    def __init__(self):
        self.db_init_start_time = ""
        self.db_init_end_time = ""
        self.warmup_run_start_time = ""
        self.warmup_run_end_time = ""
        self.measurement_run_start_time = ""
        self.measurement_run_end_time = ""
        self.chkpointcursor = ""

    @classmethod
    def execute_pgcommand(cls, pgcommands, targetserver, result_config, testname, bin_directory):
        ''' Main Module to execute PG Command, it will call following
            1. Initialize the DB
            2. Execute Warmup runs (if Required)
            3. Execute Measure runs
            4. Populate result of the test in Result DB
        '''
        executepgcommand = ExecutePGCommand()
        print("Creating test database")
        ExecutePGCommand.create_testdb(targetserver, executepgcommand, bin_directory)
        print("Test database created successfully")
        
        for key, pgcommand in pgcommands.items():
            print('********************************')
            print(f"Processing step: {key} for test: {testname}, pg_Command: {pgcommand}")
            print('********************************')
            if "initialize" in key:
                print("Initializing database with test data")
                cls.execute_dbinit_test(
                    pgcommand, targetserver, executepgcommand)
                print(f"Database initialization completed at {datetime.datetime.utcnow()}")
            if "warmupruns" in key:
                warmup = "true"
                print(f"Executing warmup tests for {testname} (duration: {targetserver['pgserver_warmupduration']}s)")
                cls.execute_test(pgcommand, targetserver,
                                 warmup, executepgcommand, bin_directory)
                print(f"Warmup tests completed for {testname}")
                print("Saving warmup test results")
                PopulateResult.load_result_in_db(
                    result_config, targetserver, pgcommand, testname, warmup)
                print("Warmup results saved")

            if "testruns" in key:
                warmup = "false"
                print(f"Executing measurement tests for {testname}")
                cls.execute_test(pgcommand, targetserver,
                                 warmup, executepgcommand, bin_directory)
                print(f"Measurement tests completed for {testname}")
                print("Saving measurement test results")
                
                # Pass monitoring data for measurement runs
                monitoring_data = getattr(executepgcommand, 'monitoring_result', None)
                
                PopulateResult.load_result_in_db(
                    result_config, targetserver, pgcommand, testname, warmup, monitoring_data)
                print("Measurement results saved")
            

    @staticmethod
    def create_testdb(targetserver, executepgcommand, bin_directory):
        """
        It will create test database on target server using command line tools
        """
        pgserver_dbname = targetserver["pgserver_dbname"]
        
        # Drop existing database if it exists
        pgcommand_drop_db = f"{bin_directory}/dropdb --if-exists" + \
            " -h " + targetserver["pgserver_hosturl"] + \
            " -p " + targetserver["pgserver_dbport"] + \
            " " + pgserver_dbname
        
        pgcommand_drop_db = ExecutePGCommand.set_pgpassword(pgcommand_drop_db, targetserver)
        
        print(f"Dropping existing database {pgserver_dbname} (if exists)")
        try:
            subprocess.run(pgcommand_drop_db, shell=True, check=False, capture_output=True)
        except Exception as e:
            print(f"Warning: Drop database command failed (database may not exist): {e}")
        
        # Create new database
        pgcommand_create_db = f"{bin_directory}/createdb" + \
            " -h " + targetserver["pgserver_hosturl"] + \
            " -p " + targetserver["pgserver_dbport"] + \
            " " + pgserver_dbname
        
        pgcommand_create_db = ExecutePGCommand.set_pgpassword(pgcommand_create_db, targetserver)
        
        print(f"Creating database {pgserver_dbname}")
        try:
            result = subprocess.run(pgcommand_create_db, shell=True, check=True, capture_output=True, text=True)
            print(f"Database {pgserver_dbname} created successfully")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create database {pgserver_dbname}: {e.stderr}")
            raise Exception(f"Database creation failed: {e.stderr}")


    @classmethod
    def execute_dbinit_test(cls, pgcommand, targetserver, executepgcommand):
        """
        It will execute the DB Initialization command once the DB has been created
        """
        _pgcommand_initialize = cls.set_pgpassword(pgcommand, targetserver)
        print(f"Running database initialization on {targetserver['pgserver_hosturl']}")
        executepgcommand.db_init_start_time = datetime.datetime.utcnow()
        cls.run_command(_pgcommand_initialize, warmup="None")
        executepgcommand.db_init_end_time = datetime.datetime.utcnow()
        print(f"Database initialization completed (duration: {executepgcommand.db_init_end_time - executepgcommand.db_init_start_time})")

    @classmethod
    def execute_test(cls, pgcommand, targetserver, warmup, executepgcommand, bin_directory):
        """
        This will perform Warmup and Measurement runs as applicable. Currently,
        Warmup is only performed for Read Only and Read Write workloads and not for Latency Tests
        """
        if warmup == "true":
            _pgcommand_warmup_run = cls.set_pgpassword(pgcommand, targetserver)
            print(f"Running warmup test on {targetserver['pgserver_hosturl']} (duration: {targetserver['pgserver_warmupduration']}s)")
            executepgcommand.warmup_run_start_time = datetime.datetime.utcnow()
            cls.run_command(_pgcommand_warmup_run, warmup)
            executepgcommand.warmup_run_end_time = datetime.datetime.utcnow()
            file = open("warmup_output_file_path.txt", 'a')
            file.write("\nDBInit StartTime = " + str(executepgcommand.db_init_start_time) +
                       "\nDBInit EndTime = " + str(executepgcommand.db_init_end_time))
            file.write("\nStartTime = " + str(executepgcommand.warmup_run_start_time) +
                       "\nEndTime = " + str(executepgcommand.warmup_run_end_time))
            file.close()
            print(f"Warmup test completed (duration: {executepgcommand.warmup_run_end_time - executepgcommand.warmup_run_start_time})")

        if warmup == "false":
            print(f"Starting measurement test on {targetserver['pgserver_hosturl']}")
            print("Executing checkpoint before measurement")
            
            # Execute CHECKPOINT using psql command line
            pgserver_dbname = targetserver["pgserver_dbname"]
            
            checkpoint_command = f"{bin_directory}/psql" + \
                " -h " + targetserver["pgserver_hosturl"] + \
                " -p " + targetserver["pgserver_dbport"] + \
                " -d " + pgserver_dbname + \
                " -c 'CHECKPOINT;'"
            
            checkpoint_command = cls.set_pgpassword(checkpoint_command, targetserver)
            
            try:
                result = subprocess.run(checkpoint_command, shell=True, check=True, capture_output=True, text=True)
                print("Checkpoint completed")
            except subprocess.CalledProcessError as e:
                print(f"ERROR: Checkpoint command failed: {e.stderr}")
                raise Exception(f"Checkpoint execution failed: {e.stderr}")
            
            # Continue with measurement run after successful checkpoint
            _pgcommand_measurement_run = cls.set_pgpassword(pgcommand, targetserver)
            print("Starting system monitoring and benchmark execution")
            executepgcommand.measurement_run_start_time = datetime.datetime.utcnow()
            
            # Create PopulateResult instance for monitoring
            monitoring_result = PopulateResult()
            
            # Start system monitoring
            monitoring_result.start_monitoring()
            
            cls.run_command(_pgcommand_measurement_run, warmup)
            
            # Stop system monitoring
            monitoring_result.stop_monitoring()
            
            executepgcommand.measurement_run_end_time = datetime.datetime.utcnow()
            
            # Store monitoring data in executepgcommand for later use
            executepgcommand.monitoring_result = monitoring_result
            
            file = open("summary_output_file_path.txt", 'a')
            file.write("\nDBInit StartTime = " + str(executepgcommand.db_init_start_time) +
                    "\nDBInit EndTime = " + str(executepgcommand.db_init_end_time))
            file.write("\nStartTime = " + str(executepgcommand.measurement_run_start_time) +
                    "\nEndTime = " + str(executepgcommand.measurement_run_end_time))
            file.close()
            print(f"Measurement test completed (duration: {executepgcommand.measurement_run_end_time - executepgcommand.measurement_run_start_time})")

    @classmethod
    def write_in_csv(cls, elapsed_time, tps, latency, stddev):
        with open("progress_metrics.csv", "a") as csvfile:
            csvfile.write(f"{time.strftime("%Y-%m-%d %H:%M:%S")},{elapsed_time},{tps},{latency},{stddev}\n")

    @classmethod
    def run_command(cls, _pgcommand, warmup):
        if warmup == "None":
            with open("summary_output_file_path.txt", 'w') as summary_out, \
                    open("progress_output_file_path.txt", 'w') as progress_out:
                init_result = subprocess.Popen(
                    _pgcommand, shell=True, stdout=summary_out, stderr=progress_out)
                out, err = init_result.communicate()
        if warmup == "false":
            with open("summary_output_file_path.txt", 'w') as summary_out, \
                    open("progress_output_file_path.txt", 'w') as progress_out:
                init_result = subprocess.Popen(
                    _pgcommand, shell=True, stdout=summary_out, stderr=progress_out)
                out, err = init_result.communicate()
            return init_result
        if warmup == "true":
            with open("warmup_output_file_path.txt", 'w') as warmup_out, \
                    open("progress_output_file_path.txt", 'w') as progress_out:
                init_result = subprocess.Popen(
                    _pgcommand, shell=True, stdout=warmup_out, stderr=progress_out)
                out, err = init_result.communicate()
            return init_result
        return False

    @classmethod
    def set_pgpassword(cls, pgcommand, targetserver):
        ''' Depending on Client OS, PGPASSWORD is set for non-interactive execution'''
        if sys.platform != 'win32':
            pgcommand_final = pgcommand
        return pgcommand_final
