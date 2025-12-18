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

def setup_postgres_from_source(repo_url=None, branch="master", base_dir=None):
    """Clone Postgres repo, compile, initialize, and start the server.
    
    Args:
        repo_url: Git repository URL (default: official Postgres repo)
        branch: Branch to checkout (default: master)
        base_dir: Base directory for installation (default: current directory)
    
    Returns:
        bin_directory: Path to the compiled Postgres bin directory
    """
    if repo_url is None:
        repo_url = "https://github.com/postgres/postgres.git"
    
    if base_dir is None:
        base_dir = os.path.join(os.getcwd(), "postgres_setup")
    
    os.makedirs(base_dir, exist_ok=True)
    
    source_dir = os.path.join(base_dir, "postgres")
    install_dir = os.path.join(base_dir, "inst")
    data_dir = os.path.join(base_dir, "data")
    bin_dir = os.path.join(install_dir, "bin")
    
    print(f"\n=== Setting up PostgreSQL from source ===")
    print(f"Repository: {repo_url}")
    print(f"Branch: {branch}")
    print(f"Installation directory: {install_dir}")
    
    # Clone the repository if it doesn't exist
    if not os.path.exists(source_dir):
        print(f"\n[1/6] Cloning repository...")
        subprocess.run(["git", "clone", repo_url, source_dir], check=True)
    else:
        print(f"\n[1/6] Repository already exists, pulling latest changes...")
        subprocess.run(["git", "-C", source_dir, "fetch"], check=True)
    
    # Checkout the specified branch
    print(f"\n[2/6] Checking out branch: {branch}")
    subprocess.run(["git", "-C", source_dir, "checkout", branch], check=True)
    subprocess.run(["git", "-C", source_dir, "pull"], check=True)
    
    # Configure
    print(f"\n[3/6] Configuring build...")
    configure_cmd = [
        "./configure",
        "--with-zlib",
        "--enable-debug",
        "--enable-depend",
        f"--prefix={install_dir}",
        "--enable-cassert",
        "--with-openssl",
        "--enable-tap-tests",
        "--with-readline",
        "CPPFLAGS=-DLOCK_DEBUG",
        "--with-libxml",
        "CFLAGS=-DAZURE_POSTGRES -ggdb3"
    ]
    subprocess.run(configure_cmd, cwd=source_dir, check=True)
    
    # Compile
    print(f"\n[4/6] Compiling (this may take several minutes)...")
    subprocess.run(["make", "-j", "8"], cwd=source_dir, check=True)
    subprocess.run(["make", "install"], cwd=source_dir, check=True)
    
    # Initialize database
    print(f"\n[5/6] Initializing database...")
    if os.path.exists(data_dir):
        print(f"Data directory already exists, skipping initdb")
    else:
        subprocess.run([os.path.join(bin_dir, "initdb"), "-D", data_dir], check=True)
    
    # Start PostgreSQL server
    print(f"\n[6/6] Starting PostgreSQL server...")
    pg_ctl = os.path.join(bin_dir, "pg_ctl")
    logfile = os.path.join(base_dir, "logfile")
    
    # Check if already running
    status_result = subprocess.run(
        [pg_ctl, "-D", data_dir, "status"],
        capture_output=True
    )
    
    if status_result.returncode != 0:
        subprocess.run([pg_ctl, "-D", data_dir, "-l", logfile, "start"], check=True)
        print("PostgreSQL server started successfully")
    else:
        print("PostgreSQL server is already running")
    
    print(f"\n=== PostgreSQL setup complete ===")
    print(f"Bin directory: {bin_dir}")
    print(f"Data directory: {data_dir}")
    print(f"Log file: {logfile}")
    
    return bin_dir

def parse_arguments():
    """Parse command line arguments for bin directory, test cases, and setup options.
    
    Usage: 
        python meru_design.py [bin_directory] [test_cases] [--setup-from-source] [--repo URL] [--branch BRANCH]
    
    Examples:
        python meru_design.py /path/to/bin
        python meru_design.py /path/to/bin "Select1, RO_FullyCached"
        python meru_design.py --setup-from-source
        python meru_design.py --setup-from-source --branch REL_16_STABLE
    """
    bin_directory = None
    test_cases = DEFAULT_TEST_CASES
    cores = 2
    setup_from_source = False
    repo_url = None
    branch = "master"
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--setup-from-source":
            setup_from_source = True
        elif arg == "--repo" and i + 1 < len(sys.argv):
            repo_url = sys.argv[i + 1]
            i += 1
        elif arg == "--branch" and i + 1 < len(sys.argv):
            branch = sys.argv[i + 1]
            i += 1
        elif arg == "--cores" and i + 1 < len(sys.argv):
            cores = int(sys.argv[i + 1])
            i += 1
        elif bin_directory is None and not arg.startswith("--"):
            bin_directory = arg
        elif not arg.startswith("--"):
            test_cases = arg
        i += 1
    
    # If setup from source is requested
    if setup_from_source:
        bin_directory = setup_postgres_from_source(repo_url=repo_url, branch=branch)
    elif bin_directory is None:
        bin_directory = input("Please enter the bin directory path for pgbench executable (or press Enter to setup from source): ")
        if not bin_directory.strip():
            bin_directory = setup_postgres_from_source()
    
    return bin_directory, test_cases, cores

BIN_DIRECTORY, test_cases, cores = parse_arguments()

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
    testcase = testcase.strip()  # Remove leading/trailing whitespace
    print(f"Starting benchmark test: {testcase}")
    pgcommands = CreatePGCommand.pgcommand_to_execute(server, testcase, PGSERVER_SELECT1FILE, BIN_DIRECTORY)
    for command_key, command_value in pgcommands.items():
        print('--------------------------------')
        print(f"Generated command for {command_key}: {command_value}")
        print('--------------------------------')
    print(f"Executing benchmark commands for {testcase}")
    ExecutePGCommand.execute_pgcommand(pgcommands, server, RESULT_CONFIG, testcase, BIN_DIRECTORY)
    print(f"Completed benchmark test: {testcase}\n")
