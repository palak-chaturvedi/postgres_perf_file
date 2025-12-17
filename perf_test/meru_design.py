import sys
import os
import subprocess
from CreatePGCommand import CreatePGCommand
from ExecutePGCommand import ExecutePGCommand
#from QueryKeyVault import QueryKeyVault

# Variables passed through Pipeline. Static values would be replaced with the parameters passed through Pipeline


print("=== PostgreSQL Performance Benchmark Suite ===")
print("Starting benchmark execution...")

PGSERVER_TESTSERVERS = 'test_suite_neu_stage.json'
RESULT_CONFIG = 'config.json'
PGSERVER_SELECT1FILE = 'select1.sql'

# Default test cases
DEFAULT_TEST_CASES = "Select1, RO_Borderline"

def parse_arguments():
    """Parse command line arguments for bin directory and test cases.
    
    Usage: python meru_design.py [bin_directory] [test_cases]
    Examples:
        python meru_design.py /path/to/bin
        python meru_design.py /path/to/bin "Select1, RO_FullyCached"
    """
    bin_directory = None
    test_cases = DEFAULT_TEST_CASES
    
    if len(sys.argv) > 1:
        bin_directory = sys.argv[1]
    else:
        bin_directory = input("Please enter the bin directory path for pgbench executable: ")
    
    if len(sys.argv) > 2:
        test_cases = sys.argv[2]
    
    return bin_directory, test_cases

BIN_DIRECTORY, test_cases = parse_arguments()

print("Test cases to be executed:", test_cases)
print("Bin directory:", BIN_DIRECTORY)

server = dict()

server["pgserver_RO_fullCacheSF"] = 30
server["pgserver_RO_BorderLineSF"] = 90
server["pgserver_RO_OutOfCacheSF"] = 2500
server["pgserver_RW_fullcacheSF"] = 30
server["pgserver_client_Multiplier"] = 8
server["pgserver_thread_Multiplier"] = 8
server["pgserver_RO_FixedSF"] = 0
server["pgserver_RW_FixedSF"] = 0
server["pgserver_QueryMode"] = "prepared"
server["pgserver_warmupduration"] = 18
server["pgserver_testduration"] = 30
server["pgserver_RW_testduration"] = 600
server["pgserver_delete_afterrun"] = 'True'
server['pgserver_hosturl'] = 'localhost'
server['pgserver_dbport'] = '5432'
server['pgserver_username'] = 'palak'
server['pgserver_password'] = 'password123'
server['pgserver_dbname'] = 'testdb'
server['pgserver_vcore'] = 2
server['pgserver_testmode'] = 'prepared'
server['bin_directory'] = BIN_DIRECTORY

print("\n=== Configuration Summary ===")
print("Bin directory is set to:", BIN_DIRECTORY)
print("Test cases to be executed:", test_cases)
print("=" * 30 + "\n")

# Learn about the pgbench version on the agent.
try:
    version_result = subprocess.run([f"{BIN_DIRECTORY}/pgbench", "--version"], stdout=subprocess.PIPE, text=True, check=True)
    version_output = version_result.stdout.decode() if isinstance(version_result.stdout, bytes) else version_result.stdout
    # Extract version number from output like "pgbench (PostgreSQL) 16.0"
    version_parts = version_output.split()
    if len(version_parts) >= 3:
        server["pgbench_version"] = int(float(version_parts[2].split('.')[0]))
    else:
        server["pgbench_version"] = 18  # Default fallback
    print(f"Detected pgbench version is {server['pgbench_version']}")
except Exception as e:
    print(f"WARNING: Failed to detect pgbench version: {e}")
    server["pgbench_version"] = 18  # Default fallback

for testcase in test_cases.split(","):
    print(f"Starting benchmark test: {testcase}")
    pgcommands = CreatePGCommand.pgcommand_to_execute(server, testcase, PGSERVER_SELECT1FILE, BIN_DIRECTORY)
    for command_key, command_value in pgcommands.items():
        print('--------------------------------')
        print(f"Generated command for {command_key}: {command_value}")
        print('--------------------------------')
    print(f"Executing benchmark commands for {testcase}")
    ExecutePGCommand.execute_pgcommand(pgcommands, server, RESULT_CONFIG, testcase, BIN_DIRECTORY)
    print(f"Completed benchmark test: {testcase}\n")
