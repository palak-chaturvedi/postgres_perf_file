# PostgreSQL Performance Data Collector (collect_tps_and_resize.py)

A comprehensive tool for collecting PostgreSQL performance metrics during dynamic shared buffer resizing and various workload tests. This tool orchestrates pgbench workloads, monitors system resources, and captures detailed performance data for analysis.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command-Line Usage](#command-line-usage)
- [Configuration](#configuration)
- [Test Cases](#test-cases)
- [Output Files](#output-files)
- [Understanding the Results](#understanding-the-results)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Overview

`collect_tps_and_resize.py` is designed to evaluate PostgreSQL performance under different shared buffer configurations. It runs continuous pgbench benchmarks while dynamically resizing shared buffers, collecting TPS (Transactions Per Second), latency, CPU usage, and buffer resize timings.

**Key capabilities:**
- Runs multiple test cases (Select1, RO_FullyCached, RO_Borderline, RW_FullyCached)
- Dynamically resizes shared buffers without server restart
- Continuous 5-minute measurements for each buffer size
- 2-minute warmup period before measurements
- Real-time monitoring of CPU, memory, and performance metrics
- Comprehensive CSV logging for visualization

## Features

- **Dynamic Buffer Resizing**: Changes shared_buffers on-the-fly using `pg_resize_shared_buffers` extension
- **Multiple Test Cases**: Supports various workload patterns (read-only, read-write, fully cached, borderline)
- **Continuous Monitoring**: CPU, memory, TPS, and latency tracking
- **Warmup Period**: 2-minute warmup before each test case measurement
- **Detailed Logging**: Class-based logging with timestamps and severity levels
- **CSV Output**: Structured data for downstream analysis and visualization
- **Interactive Mode**: Prompts for missing configuration parameters
- **Flexible Configuration**: Command-line arguments or interactive prompts

## Prerequisites

### Required Software

1. **PostgreSQL** with `pg_resize_shared_buffers` extension
   - Custom build with dynamic resize capability
   - Must be compiled with `-DAZURE_POSTGRES` flag

2. **Python 3.8+** with the following packages:
   - `psutil` - For system monitoring
   - Standard library packages (argparse, csv, logging, subprocess, threading)

3. **pgbench** - Included with PostgreSQL installation

### System Requirements

- Linux environment (tested on Ubuntu/Debian)
- Sufficient disk space for test database and results
- Root or sudo access for PostgreSQL operations (optional)

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install psutil
   ```

2. **Verify PostgreSQL installation:**
   ```bash
   # Check PostgreSQL binaries
   ls /path/to/postgres/inst/bin/
   # Should show: psql, pg_ctl, pgbench, etc.
   
   # Verify pg_resize_shared_buffers extension
   psql -c "SELECT * FROM pg_available_extensions WHERE name = 'pg_resize_shared_buffers';"
   ```

3. **Clone or download the script:**
   ```bash
   cd /home/palak/test_perf
   # collect_tps_and_resize.py should be in this directory
   ```

## Quick Start

### Basic Usage (Interactive Mode)

The script does not initate any database. Initate a db, update the postgresql.conf for max_connection, checkpoints and max_shared_buffers if needed. Then start using pg_ctl. Also change the scale, clients and threads in the code. There is no input for that.


Run without arguments to be prompted for configuration:

```bash
python3 collect_tps_and_resize.py
```

You'll be asked for:
- PostgreSQL bin directory path
- Result directory (default: current directory)
- Number of virtual cores (default: 2)

### Example Interactive Session

```
$ python3 collect_tps_and_resize.py

Please enter the PostgreSQL bin directory path (e.g., /home/user/postgres/inst/bin): /home/palak/postgres/inst/bin
Please enter the result directory path (press Enter to use current directory: /home/palak/test_perf): /home/palak/perf
Please enter the number of virtual cores (press Enter to use default: 2): 4

INFO: Configuration summary:
INFO:   Bin directory: /home/palak/postgres/inst/bin
INFO:   Result directory: /home/palak/perf
INFO:   Virtual cores: 4
INFO: [Config] Data directory: /home/palak/postgres/test
INFO: [Config] Collection directory: /home/palak/perf/data_2025-12-18_10:30_128_128_128_300
...
```

## Command-Line Usage

### Syntax

```bash
python3 collect_tps_and_resize.py [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--bin-dir PATH` | PostgreSQL bin directory | Interactive prompt |
| `--result-dir PATH` | Directory to store results | Current directory |
| `--vcore N` | Number of virtual cores | 2 |

### Examples

**1. Specify bin directory only:**
```bash
python3 collect_tps_and_resize.py --bin-dir /home/palak/postgres/inst/bin
```

**2. Specify all parameters:**
```bash
python3 collect_tps_and_resize.py \
  --bin-dir /home/palak/postgres/inst/bin \
  --result-dir /home/palak/perf \
  --vcore 4
```

**3. Custom result directory:**
```bash
python3 collect_tps_and_resize.py \
  --bin-dir /opt/postgres/bin \
  --result-dir /data/perf_results
```

**4. High-core system:**
```bash
python3 collect_tps_and_resize.py \
  --bin-dir /usr/local/pgsql/bin \
  --vcore 16
```

## Configuration

The script uses a `Config` dataclass with the following parameters:

### Connection Settings
```python
host: str = "localhost"
port: str = "5432"
username: str = "palak"
password: str = "password123"
dbname: str = "testdb"
maintenance_db: str = "postgres"
```

### Test Parameters
```python
scale: int = 128              # Database scale factor
client_count: int = 128       # Number of pgbench clients
thread_count: int = 128       # Number of pgbench threads
duration: int = 300           # 5 minutes per buffer change
warmup_duration: int = 120    # 2 minutes warmup
wait_between_changes: int = 60  # 1 minute wait between changes
```

### Buffer Sequence
```python
shared_buffer_sequence: Tuple[int, ...] = (4, 8, 12, 9, 4)
# Shared buffer sizes in GB to test
```

### Test Cases
```python
test_cases: Tuple[str, ...] = ("Select1", "RO_FullyCached")
# Available: "Select1", "RO_FullyCached", "RO_Borderline", "RW_FullyCached"
```

### Modifying Configuration

To change these settings, edit the `Config` class in `collect_tps_and_resize.py`:

```python
@dataclass
class Config:
    # ... existing parameters ...
    
    # Example: Change test duration to 10 minutes
    duration: int = 600
    
    # Example: Add more test cases
    test_cases: Tuple[str, ...] = ("Select1", "RO_FullyCached", "RO_Borderline")
    
    # Example: Different buffer sequence
    shared_buffer_sequence: Tuple[int, ...] = (2, 4, 8, 16, 8, 4)
```

## Test Cases

The tool supports multiple test case types:

### 1. Select1
- **Workload**: Simple `SELECT 1` query
- **Purpose**: Minimal overhead baseline test
- **File**: `select1.sql` (must exist in current directory)
- **Scale Factor**: N/A
- **Mode**: Prepared statements

### 2. RO_FullyCached
- **Workload**: Read-only, fully cached dataset
- **Purpose**: Tests read performance with all data in cache
- **Scale Factor**: 10 (configurable via `ro_fullcache_sf`)
- **Mode**: Standard pgbench read-only workload

### 3. RO_Borderline
- **Workload**: Read-only, dataset at cache boundary
- **Purpose**: Tests performance with cache misses
- **Scale Factor**: 20 (configurable via `ro_borderline_sf`)
- **Mode**: Standard pgbench read-only workload

### 4. RW_FullyCached
- **Workload**: Read-write, fully cached dataset
- **Purpose**: Tests mixed workload performance
- **Scale Factor**: 5 (configurable via `rw_fullcache_sf`)
- **Mode**: Standard pgbench read-write workload

### Test Case Execution Flow

For each test case:
1. **Database Initialization**: Create and populate test database
2. **Warmup**: Run 2-minute warmup period (not measured)
3. **Continuous Measurement Loop**:
   - Run 5-minute pgbench benchmark
   - Monitor TPS, latency, CPU usage
   - Resize controller changes buffer size
   - Wait 1 minute between changes
   - Repeat for all buffer sizes in sequence
4. **Cleanup**: Drop test database

## Output Files

Results are stored in a timestamped directory:
```
/home/palak/perf/data_YYYY-MM-DD_HH:MM_scale_clients_threads_duration/
```

### File Structure

| File | Description | Format |
|------|-------------|--------|
| `tps_latency_logs.csv` | TPS and latency metrics | timestamp, test_case, run_type, elapsed_seconds, tps, latency_avg, latency_stddev |
| `cpu_usage_logs.csv` | CPU utilization | timestamp, cpu_percent |
| `shared_buffer_sizes.csv` | Buffer resize events | timestamp, shared_buffers_gb |
| `restart_timings.csv` | Restart events (if any) | timestamp, status, shared_buffers_gb, test_case |
| `resize_timings.csv` | Buffer resize timing | timestamp, old_size_gb, new_size_gb, test_case |

### CSV Column Descriptions

**tps_latency_logs.csv:**
- `timestamp`: ISO 8601 timestamp
- `test_case`: Name of test case (Select1, RO_FullyCached, etc.)
- `run_type`: "warmup" or "measurement"
- `elapsed_seconds`: Seconds elapsed since test start
- `tps`: Transactions per second
- `latency_avg`: Average latency in milliseconds
- `latency_stddev`: Latency standard deviation in milliseconds

**cpu_usage_logs.csv:**
- `timestamp`: ISO 8601 timestamp
- `cpu_percent`: CPU utilization percentage (0-100)

**restart_timings.csv:**
- `timestamp`: ISO 8601 timestamp
- `status`: "restart_start" or "restart_end"
- `shared_buffers_gb`: Buffer size in GB
- `test_case`: Test case name

## Understanding the Results

### Performance Metrics

**TPS (Transactions Per Second):**
- Higher is better
- Indicates throughput capacity
- Varies with buffer size and workload

**Latency (milliseconds):**
- Lower is better
- Average response time per transaction
- Standard deviation shows consistency

**CPU Usage (%):**
- Shows system resource utilization
- High CPU with high TPS = efficient
- High CPU with low TPS = bottleneck

### Analyzing Buffer Impact

1. **Plot TPS vs. Buffer Size**: See how throughput changes
2. **Examine Latency Trends**: Identify optimal buffer range
3. **Check CPU Correlation**: Understand resource efficiency
4. **Compare Test Cases**: Different workloads, different optima

### Typical Patterns

- **Too Small Buffers**: High latency, low TPS (cache misses)
- **Optimal Buffers**: High TPS, low latency, reasonable CPU
- **Too Large Buffers**: Diminishing returns, wasted memory

## Troubleshooting

### Common Issues

**1. "Bin directory does not exist"**
```bash
# Verify path
ls /home/palak/postgres/inst/bin/
# Should show PostgreSQL binaries
```

**2. "pgbench not found"**
```bash
# Check pgbench location
which pgbench
# Or specify full path in --bin-dir
```

**3. "Connection refused"**
```bash
# Check if PostgreSQL is running
/home/palak/postgres/inst/bin/pg_ctl -D /home/palak/postgres/test status

# Start if needed
/home/palak/postgres/inst/bin/pg_ctl -D /home/palak/postgres/test start
```

**4. "Permission denied" for result directory**
```bash
# Create directory with proper permissions
mkdir -p /home/palak/perf
chmod 755 /home/palak/perf
```

**5. "pg_resize_shared_buffers extension not found"**
```sql
-- Check available extensions
SELECT * FROM pg_available_extensions WHERE name LIKE '%resize%';

-- If missing, rebuild PostgreSQL with dynamic resize support
```

**6. Test hangs or times out**
- Check PostgreSQL logs: `tail -f /home/palak/postgres/test/log/postgresql.log`
- Verify database connectivity: `psql -h localhost -p 5432 -U palak -d postgres`
- Check system resources: `top`, `df -h`

**7. Incomplete results**
- Verify sufficient disk space: `df -h`
- Check for errors in terminal output
- Review log messages for class-specific issues

### Debug Mode

For verbose output, modify logging level in the script:
```python
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
```

### Log Messages

Log messages are prefixed with class names for traceability:
- `[Config]` - Configuration initialization
- `[DatabaseManager]` - Database operations
- `[BenchmarkRunner]` - pgbench execution
- `[ResizeController]` - Buffer resize operations
- `[MonitoringManager]` - System monitoring
- `[PerformanceCollector]` - Main orchestration

## Advanced Usage

### Custom Test Cases

To add a new test case:

1. **Define test in Config:**
```python
test_cases: Tuple[str, ...] = ("Select1", "MyCustomTest")
```

2. **Implement in BenchmarkRunner:**
```python
def _get_test_config(self, test_case: str) -> dict:
    if test_case == "MyCustomTest":
        return {
            "scale": 50,
            "mode": "prepared",
            "custom_script": "my_test.sql"
        }
```

### Continuous Monitoring

The tool runs monitoring in background threads:
- **CPU Monitor**: Samples every 1 second
- **TPS/Latency Monitor**: Parses pgbench progress output
- **Resize Monitor**: Tracks buffer size changes

### Integration with Visualization

Results are designed for use with `plot_tps_latency_gaps.py`:

```bash
# After data collection
python3 plot_tps_latency_gaps.py -d /home/palak/perf/data_2025-12-18_10:30_128_128_128_300

# Generates graphs:
# - TPS over time by test case
# - Latency over time by test case
# - With/without restart markers
# - Y-axis from 0 variants
```

### Parallel Execution

To run multiple configurations in parallel:
```bash
# Terminal 1: Configuration A
python3 collect_tps_and_resize.py --bin-dir /path/to/postgres1/bin --result-dir /results/config_a --vcore 4

# Terminal 2: Configuration B (different port)
python3 collect_tps_and_resize.py --bin-dir /path/to/postgres2/bin --result-dir /results/config_b --vcore 8
```

**Note**: Ensure different PostgreSQL ports or data directories to avoid conflicts.

### Scripted Execution

Create a wrapper script for batch testing:

```bash
#!/bin/bash
# run_all_tests.sh

BIN_DIR="/home/palak/postgres/inst/bin"
RESULT_BASE="/home/palak/perf"

for vcore in 2 4 8 16; do
    echo "Running with $vcore vcores..."
    python3 collect_tps_and_resize.py \
        --bin-dir "$BIN_DIR" \
        --result-dir "$RESULT_BASE/vcore_$vcore" \
        --vcore $vcore
    
    echo "Completed $vcore vcore test"
    sleep 60
done
```

### Memory and CPU Considerations

**For high-throughput testing:**
- Increase `client_count` and `thread_count`
- Ensure sufficient system memory for large `shared_buffer_sequence`
- Monitor system resources: `htop`, `vmstat 1`

**For low-resource systems:**
- Reduce `client_count` and `thread_count`
- Use smaller `shared_buffer_sequence`
- Increase `wait_between_changes` to allow system recovery

## Example Workflows

### Workflow 1: Baseline Performance Test

```bash
# Start with default configuration
python3 collect_tps_and_resize.py \
    --bin-dir /home/palak/postgres/inst/bin \
    --result-dir /home/palak/perf/baseline \
    --vcore 2

# Wait for completion (approximately 30-40 minutes for default config)
# Visualize results
cd /home/palak/perf
python3 plot_tps_latency_gaps.py -d baseline/data_*
```

### Workflow 2: Multi-Core Comparison

```bash
for cores in 2 4 8 16; do
    python3 collect_tps_and_resize.py \
        --bin-dir /home/palak/postgres/inst/bin \
        --result-dir /home/palak/perf/cores_$cores \
        --vcore $cores
done

# Compare results across core counts
```

### Workflow 3: Custom Buffer Sequence

Edit `collect_tps_and_resize.py`:
```python
shared_buffer_sequence: Tuple[int, ...] = (1, 2, 4, 8, 16, 32)
```

Run:
```bash
python3 collect_tps_and_resize.py --bin-dir /path/to/bin --result-dir /results/extended_buffers
```

## Support and Contribution

For issues, questions, or contributions:
- Check logs for detailed error messages
- Review PostgreSQL logs for database-specific issues
- Ensure all prerequisites are met
- Verify PostgreSQL custom build with dynamic resize support

## Visualization with plot_tps_latency_gaps.py

After collecting performance data with `collect_data.py`, use `plot_tps_latency_gaps.py` to visualize the results.

### Overview

`plot_tps_latency_gaps.py` generates graphs showing:
- **TPS (Transactions Per Second)** over time
- **Latency (milliseconds)** over time
- **Warmup periods** highlighted in light green
- **Restart/resize windows** (optional) shaded in red
- **Missing data gaps** where TPS drops to zero

### Quick Start

```bash
# Basic usage - generate graphs for a data directory
python3 plot_tps_latency_gaps.py -d /home/palak/perf/data_2025-12-18_10:30_128_128_128_300

# Alternative: run from within the data directory
cd /home/palak/perf/data_2025-12-18_10:30_128_128_128_300
python3 ../plot_tps_latency_gaps.py -d .
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d PATH` | Path to directory containing CSV files | `tps_latency_logs.csv` |
| `--restart-csv PATH` | Path to restart_timings.csv (optional) | Auto-detected |
| `--output PATH` | Output PNG filename | `graphs/tps_latency_missing.png` |
| `--bin-seconds N` | Bin width for grouping samples (seconds) | 2 |
| `--missing-threshold N` | Treat TPS ≤ this value as missing | 0.0 |
| `--max-latency N` | Ignore latency samples above ceiling | None (keep all) |
| `--show` | Display plot interactively after saving | False |

### Usage Examples

**1. Basic visualization:**
```bash
python3 plot_tps_latency_gaps.py -d /home/palak/perf/data_2025-12-18_10:30_128_128_128_300
```

**2. With custom binning (5-second intervals):**
```bash
python3 plot_tps_latency_gaps.py -d /path/to/data -d --bin-seconds 5
```

**3. Clip high latency outliers:**
```bash
python3 plot_tps_latency_gaps.py -d /path/to/data --max-latency 100
```

**4. Show plot interactively:**
```bash
python3 plot_tps_latency_gaps.py -d /path/to/data --show
```

**5. Custom output location:**
```bash
python3 plot_tps_latency_gaps.py -d /path/to/data --output /tmp/my_plot.png
```

### Output Files

The script generates **4 graphs per test case**:

1. **`tps_latency_{testcase}_with_restarts.png`**
   - Shows TPS and latency with restart/resize windows (red shading)
   - Warmup periods in light green
   - Auto-scaled Y-axis

2. **`tps_latency_{testcase}_without_restarts.png`**
   - Same as above but without restart markers
   - Cleaner view of performance trends
   - Auto-scaled Y-axis

3. **`tps_latency_{testcase}_with_restarts_from_zero.png`**
   - With restart markers
   - Y-axis starts from 0 (shows full scale)
   - Better for comparing absolute values

4. **`tps_latency_{testcase}_without_restarts_from_zero.png`**
   - No restart markers
   - Y-axis starts from 0
   - Clean comparison view

### Understanding the Graphs

**Graph Components:**

- **Blue Line (Top)**: TPS (Transactions Per Second) - throughput
- **Orange Line (Bottom)**: Latency (milliseconds) - response time
- **Light Green Background**: Warmup period (first 2 minutes)
- **Red Shaded Areas**: Restart/resize windows (if present)
- **X-axis**: Time in seconds since test start
- **Left Y-axis**: TPS scale
- **Right Y-axis**: Latency scale

**Interpreting Results:**

1. **High TPS, Low Latency**: Optimal performance
2. **TPS Drop During Resize**: Expected during buffer changes
3. **Latency Spike**: May indicate system stress or I/O bottleneck
4. **Flat TPS Line**: Steady state performance (good)
5. **Warmup Period**: Ignore for analysis - cache warming up

### Test Case Separation

The script automatically:
- Detects all test cases in the CSV
- Generates separate graphs for each test case
- Filters restart events by test case
- Creates properly labeled output files

**Example output:**
```
Found 2 test case(s): Select1, RO_FullyCached

Processing test case: Select1
  Detected 5 missing TPS bins; highlighting in the plot.
  Overlaying 4 restart window(s); longest duration: 15.2s.
  Plot with restarts saved to tps_latency_Select1_with_restarts.png
  Plot without restarts saved to tps_latency_Select1_without_restarts.png
  Plot with restarts (Y from 0) saved to tps_latency_Select1_with_restarts_from_zero.png
  Plot without restarts (Y from 0) saved to tps_latency_Select1_without_restarts_from_zero.png

Processing test case: RO_FullyCached
  No missing TPS bins detected; rendering full series.
  Overlaying 4 restart window(s); longest duration: 18.5s.
  Plot with restarts saved to tps_latency_RO_FullyCached_with_restarts.png
  ...

All 2 test case(s) processed successfully.
```

### Required CSV Files

The script expects these files in the data directory:

**tps_latency_logs.csv** (required):
```csv
timestamp,test_case,run_type,elapsed_seconds,tps,latency_avg,latency_stddev
2025-12-18T10:30:00,Select1,warmup,5,12453.2,10.2,2.3
2025-12-18T10:30:05,Select1,warmup,10,12678.5,9.8,2.1
2025-12-18T10:32:00,Select1,measurement,125,13245.7,9.5,1.9
...
```

**restart_timings.csv** (optional):
```csv
timestamp,status,shared_buffers_gb,test_case
2025-12-18T10:35:00,restart_start,8,Select1
2025-12-18T10:35:15,restart_end,8,Select1
...
```

### Advanced Features

**1. Binning Strategy:**
- Groups samples into time bins (default: 2 seconds)
- Reduces noise and smooths trends
- Takes latest sample in each bin
- Adjust with `--bin-seconds` for different granularity

**2. Missing Data Detection:**
- Automatically detects gaps where TPS = 0
- Highlights missing bins in console output
- Useful for identifying measurement issues

**3. Latency Clipping:**
- Remove outliers with `--max-latency`
- Prevents extreme spikes from distorting scale
- Example: `--max-latency 100` ignores latency > 100ms

**4. Restart Window Display:**
- Shows when buffers were resized
- Duration calculated from start/end events
- Helps correlate performance drops with resize operations

### Troubleshooting

**"Could not find TPS/latency file":**
```bash
# Verify CSV exists
ls -la /path/to/data/tps_latency_logs.csv

# Check directory path
python3 plot_tps_latency_gaps.py -d /correct/path/to/data
```

**"No test cases found in the data":**
```bash
# Check CSV format
head -5 /path/to/data/tps_latency_logs.csv

# Ensure test_case column is populated
```

**Empty or incomplete graphs:**
- Check for data in the time range: `wc -l tps_latency_logs.csv`
- Verify timestamp format is correct
- Ensure measurement data (not just warmup) is present

**Latency scale too large:**
```bash
# Clip outliers
python3 plot_tps_latency_gaps.py -d /path/to/data --max-latency 50
```

**Graph not updating:**
```bash
# Delete old graphs
rm /path/to/data/tps_latency_*.png

# Regenerate
python3 plot_tps_latency_gaps.py -d /path/to/data
```

### Integration Workflow

**Complete workflow from data collection to visualization:**

```bash
# Step 1: Collect performance data
python3 collect_tps_and_resize.py \
    --bin-dir /home/palak/postgres/inst/bin \
    --result-dir /home/palak/perf \
    --vcore 4

# Step 2: Wait for completion (or monitor logs)
tail -f /home/palak/perf/data_*/logfile

# Step 3: Visualize results
DATA_DIR=$(ls -td /home/palak/perf/data_* | head -1)
python3 plot_tps_latency_gaps.py -d "$DATA_DIR"

# Step 4: View graphs
ls -lh "$DATA_DIR"/tps_latency_*.png
# Open with image viewer: eog, feh, or scp to local machine
```

### Batch Visualization

**Visualize multiple data directories:**

```bash
#!/bin/bash
# visualize_all.sh

for dir in /home/palak/perf/data_*; do
    if [ -f "$dir/tps_latency_logs.csv" ]; then
        echo "Processing $dir..."
        python3 plot_tps_latency_gaps.py -d "$dir"
    fi
done

echo "All visualizations complete!"
```

### Graph Analysis Tips

**1. Compare buffer sizes:**
- Look for TPS changes after each resize window
- Optimal buffer size shows highest sustained TPS

**2. Identify performance patterns:**
- Steady TPS = stable workload
- Gradual TPS decline = resource exhaustion
- Periodic TPS spikes = external interference

**3. Latency correlation:**
- Inverse correlation with TPS is normal
- High latency + low TPS = bottleneck
- Low latency + low TPS = underutilization

**4. Use Y-from-zero graphs for:**
- Absolute performance comparison
- Showing true scale differences
- Presentations and reports

**5. Use auto-scaled graphs for:**
- Detailed trend analysis
- Identifying small variations
- Debugging performance issues

## Related Tools

- **plot_tps_latency_gaps.py**: Visualization tool for collected data (documented above)
- **meru_design.py**: Automated PostgreSQL setup and benchmarking
- **CreatePGCommand.py**: PostgreSQL server configuration generator
- **ExecutePGCommand.py**: pgbench command executor with monitoring

## License

This tool is part of the PostgreSQL performance analysis toolkit.
