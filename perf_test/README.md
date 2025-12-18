# PostgreSQL Performance Benchmark Suite

A comprehensive tool for running PostgreSQL performance benchmarks using pgbench with automated setup, execution, and monitoring capabilities.

## Overview

`meru_design.py` is the main entry point for running PostgreSQL performance benchmarks. It supports:
- Automated PostgreSQL setup from source (clone, compile, initialize, start)
- Multiple test case execution (Select1, RO_FullyCached, RO_Borderline, RW_FullyCached, etc.)
- Performance metrics collection and analysis
- Result storage and visualization

## Prerequisites

- Python 3.x
- Git
- Build tools for PostgreSQL compilation (gcc, make, etc.)
- System dependencies: zlib, openssl, readline, libxml2

### Install Dependencies (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y build-essential git libreadline-dev zlib1g-dev \
    libssl-dev libxml2-dev
```

## Quick Start

### Option 1: Use Existing PostgreSQL Installation

```bash
python3 meru_design.py /path/to/postgres/bin
```

### Option 2: Automatic Setup from Source

```bash
python3 meru_design.py --setup-from-source
```

### Option 3: Interactive Mode

```bash
python3 meru_design.py
# You'll be prompted to enter the bin directory or press Enter to setup from source
```

## Usage Examples

### Basic Usage

Run default test cases (Select1, RO_Borderline) with existing PostgreSQL:

```bash
python3 meru_design.py /home/user/postgres/inst/bin
```

### Custom Test Cases

Run specific test cases:

```bash
python3 meru_design.py /home/user/postgres/inst/bin "Select1, RO_FullyCached"
```

Run single test case:

```bash
python3 meru_design.py /home/user/postgres/inst/bin "RO_Borderline"
```

### Setup from Source

Setup PostgreSQL from official repository (master branch):

```bash
python3 meru_design.py --setup-from-source
```

Setup from specific branch:

```bash
python3 meru_design.py --setup-from-source --branch REL_16_STABLE
```

Setup from custom repository:

```bash
python3 meru_design.py --setup-from-source \
    --repo https://github.com/username/postgres.git \
    --branch feature-branch
```

### Advanced Examples

Run multiple test cases with auto-setup:

```bash
python3 meru_design.py --setup-from-source \
    --branch master \
    "Select1, RO_FullyCached, RO_Borderline"
```

## Command Line Arguments

```
python3 meru_design.py [bin_directory] [test_cases] [options]
```

### Positional Arguments

- `bin_directory`: Path to PostgreSQL bin directory (e.g., `/path/to/postgres/inst/bin`)
- `test_cases`: Comma-separated list of test cases (default: `"Select1, RO_Borderline"`)

### Optional Arguments

- `--setup-from-source`: Automatically clone, compile, and setup PostgreSQL
- `--repo URL`: Git repository URL (default: official PostgreSQL repo)
- `--branch BRANCH`: Branch to checkout (default: `master`)

## Supported Test Cases

| Test Case | Description | Scale Factor |
|-----------|-------------|--------------|
| `Select1` | Simple SELECT 1 latency test | None (1 connection, 1 thread) |
| `Select1NPPS` | SELECT 1 with multiple connections | None |
| `RO_FullyCached` | Read-only fully cached workload | Based on vCores × multiplier |
| `RO_Borderline` | Read-only borderline cache workload | Based on vCores × multiplier |
| `RW_FullyCached` | Read-write fully cached workload | Based on vCores × multiplier |
| `RO_FixedSF` | Read-only with fixed scale factor | From config |
| `RW_FixedSF` | Read-write with fixed scale factor | From config |

## Configuration

Edit the server configuration in `meru_design.py`:

```python
server["pgserver_RO_fullCacheSF"] = 30          # RO fully cached scale factor multiplier
server["pgserver_RO_BorderLineSF"] = 90         # RO borderline scale factor multiplier
server["pgserver_RW_fullcacheSF"] = 30          # RW fully cached scale factor multiplier
server["pgserver_client_Multiplier"] = 8        # Connection count multiplier
server["pgserver_thread_Multiplier"] = 8        # Thread count multiplier
server["pgserver_warmupduration"] = 180         # Warmup duration (seconds)
server["pgserver_testduration"] = 300           # Test duration (seconds)
server["pgserver_RW_testduration"] = 600        # RW test duration (seconds)
server["pgserver_hosturl"] = "localhost"        # Database host
server["pgserver_dbport"] = "5432"              # Database port
server["pgserver_username"] = "palak"           # Database username
server["pgserver_password"] = "password123"     # Database password
server["pgserver_dbname"] = "testdb"            # Database name
server["pgserver_vcore"] = 16                   # Virtual cores
server["pgserver_testmode"] = "prepared"        # Query mode (prepared/simple/extended)
```

## Output Files

The tool generates several output files:

- `progress_metrics.csv`: Real-time TPS, latency metrics
- `warmup_output_file_path.txt`: Warmup run timings
- `summary_output_file_path.txt`: Measurement run timings
- Results are also stored in the configured result database

## PostgreSQL Setup Details

When using `--setup-from-source`, the tool performs:

1. **Clone**: Downloads PostgreSQL source code
2. **Configure**: Configures build with:
   - Debug symbols enabled
   - Assertions enabled
   - OpenSSL support
   - XML support
   - Custom CFLAGS for Azure PostgreSQL
3. **Compile**: Builds using 8 parallel jobs
4. **Install**: Installs to `postgres_setup/inst/`
5. **Initialize**: Creates database cluster in `postgres_setup/data/`
6. **Start**: Starts PostgreSQL server

Directory structure created:
```
postgres_setup/
├── postgres/       # Source code
├── inst/           # Installation
│   └── bin/        # Executables (pgbench, psql, etc.)
├── data/           # Database cluster
└── logfile         # Server log
```

## Troubleshooting

### Error: "FileNotFoundError: configure"

Ensure you have build tools installed and the repository was cloned successfully.

### Error: "TypeError: cannot unpack non-iterable NoneType"

Make sure test case names are spelled correctly and match supported test cases.

### Error: "Database creation failed"

Check that:
- PostgreSQL server is running
- Connection parameters are correct
- User has necessary permissions

### Performance Issues

- Increase `pgserver_warmupduration` for more stable results
- Adjust `pgserver_testduration` for longer measurement periods
- Check system resources (CPU, memory, disk I/O)

## Examples by Use Case

### Quick Performance Test

```bash
# Test latency with existing setup
python3 meru_design.py /usr/local/pgsql/bin "Select1"
```

### Comprehensive Benchmark

```bash
# Run full suite of tests
python3 meru_design.py /usr/local/pgsql/bin \
    "Select1, RO_FullyCached, RO_Borderline, RW_FullyCached"
```

### Development Testing

```bash
# Setup from feature branch and test
python3 meru_design.py --setup-from-source \
    --repo https://github.com/myorg/postgres.git \
    --branch feature/new-optimizer \
    "RO_FullyCached"
```

### Regression Testing

```bash
# Test specific PostgreSQL version
python3 meru_design.py --setup-from-source \
    --branch REL_15_STABLE \
    "Select1, RO_FullyCached, RO_Borderline"
```

## Additional Resources

- [pgbench Documentation](https://www.postgresql.org/docs/current/pgbench.html)
- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)


