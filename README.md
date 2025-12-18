# PostgreSQL Performance Testing Framework

A comprehensive suite of tools for PostgreSQL performance benchmarking and analysis, including automated setup, dynamic buffer resizing tests, and detailed visualization.

## Overview

This repository contains two complementary performance testing approaches:

1. **Standard Performance Benchmarks** (`perf_test/`) - Automated PostgreSQL setup and standard pgbench testing
2. **Dynamic Resize Performance Tests** (`perf_test_with_resize_restart/`) - Continuous testing with dynamic shared buffer resizing

## Repository Structure

```
postgres_perf_file/
├── perf_test/                          # Standard benchmarking suite
│   ├── meru_design.py                 # Main benchmark orchestrator
│   ├── CreatePGCommand.py             # Server configuration generator
│   ├── ExecutePGCommand.py            # pgbench command executor
│   ├── PopulateResult.py              # Result collection
│   ├── performance_analysis.py        # Performance analysis tools
│   └── README.md                      # Detailed documentation
│
└── perf_test_with_resize_restart/     # Dynamic resize testing
    ├── collect_tps_and_resize.py      # TPS collection with buffer resizing
    ├── plot_tps_latency_gaps.py       # Visualization tool
    └── README.md                      # Detailed documentation
```

## Quick Start

### 1. Standard Performance Benchmarks

Run comprehensive pgbench tests with automated PostgreSQL setup:

```bash
cd perf_test

# Option 1: Use existing PostgreSQL installation
python3 meru_design.py /path/to/postgres/bin

# Option 2: Automatic setup from source
python3 meru_design.py --setup-from-source

# Option 3: Custom test cases
python3 meru_design.py /path/to/bin Select1,RO_FullyCached,RW_FullyCached
```

**Features:**
- Automated PostgreSQL clone, compile, and setup
- Multiple test case support (Select1, RO_FullyCached, RO_Borderline, RW_FullyCached)
- Automatic scale factor calculation
- Performance results in CSV format
- Progress monitoring and warmup periods

**Output:** `performance_results.csv` with TPS, latency, and throughput metrics

### 2. Dynamic Resize Performance Tests

Collect performance data while dynamically resizing shared buffers:

```bash
cd perf_test_with_resize_restart

# Interactive mode (prompts for configuration)
python3 collect_tps_and_resize.py

# With command-line arguments
python3 collect_tps_and_resize.py \
    --bin-dir /path/to/postgres/bin \
    --result-dir /path/to/results \
    --vcore 4

# Visualize results
python3 plot_tps_latency_gaps.py -d /path/to/results/data_*/
```

**Features:**
- Dynamic shared_buffers resizing without restart
- Continuous 5-minute measurements per buffer size
- 2-minute warmup before each test
- CPU, TPS, and latency monitoring
- Detailed CSV logging with timestamps
- Automatic graph generation (4 variants per test case)

**Output:** Multiple CSV files (TPS, latency, CPU, resize timings) and PNG graphs

## Use Cases

### Use Case 1: Initial Performance Baseline
```bash
# Setup PostgreSQL and run standard benchmarks
cd perf_test
python3 meru_design.py --setup-from-source

# Creates: performance_results.csv with baseline metrics
```

### Use Case 2: Buffer Size Optimization
```bash
# Test performance across different buffer sizes
cd perf_test_with_resize_restart
python3 collect_tps_and_resize.py --bin-dir /path/to/bin --vcore 8

# Creates: TPS/latency graphs showing optimal buffer size
```

### Use Case 3: Workload Comparison
```bash
# Compare different workload patterns
cd perf_test
python3 meru_design.py /path/to/bin Select1,RO_FullyCached,RO_Borderline,RW_FullyCached

# Analyze results to identify best-performing workload
```

## Test Cases

Both tools support the following test cases:

| Test Case | Workload Type | Dataset | Purpose |
|-----------|--------------|---------|---------|
| **Select1** | Minimal | N/A | Baseline performance with simple `SELECT 1` |
| **RO_FullyCached** | Read-only | Fully cached | Tests read performance with all data in memory |
| **RO_Borderline** | Read-only | Partially cached | Tests performance with cache misses |
| **RW_FullyCached** | Read-write | Fully cached | Tests mixed workload performance |

## Key Metrics Collected

- **TPS (Transactions Per Second)**: Throughput capacity
- **Latency (ms)**: Average response time
- **Latency StdDev**: Response time consistency
- **CPU Usage (%)**: System resource utilization
- **Buffer Sizes (GB)**: Shared buffer configurations tested
- **Resize Timings**: Duration of buffer resize operations

## Prerequisites

### System Requirements
- Linux environment (tested on Ubuntu/Debian)
- Python 3.8 or higher
- Git (for source installation)
- PostgreSQL build dependencies

### Python Dependencies
```bash
pip install psutil pandas matplotlib
```

### PostgreSQL Requirements
- PostgreSQL 12+ recommended
- For dynamic resizing: Custom build with `pg_resize_shared_buffers` extension
- Compilation flag: `-DAZURE_POSTGRES`

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd postgres_perf_file
   ```

2. **Install Python dependencies:**
   ```bash
   pip install psutil pandas matplotlib
   ```

3. **Choose your testing approach:**
   - For standard benchmarks: See `perf_test/README.md`
   - For resize testing: See `perf_test_with_resize_restart/README.md`

## Documentation

Each testing suite has comprehensive documentation:

- **[perf_test/README.md](perf_test/README.md)** - Complete guide for standard benchmarking
  - Command-line reference
  - Test case details
  - Configuration options
  - Troubleshooting

- **[perf_test_with_resize_restart/README.md](perf_test_with_resize_restart/README.md)** - Complete guide for resize testing
  - Usage examples
  - Output file formats
  - Visualization guide
  - Analysis tips

## Workflow Examples

### Complete Performance Analysis Workflow

```bash
# Step 1: Setup PostgreSQL from source
cd perf_test
python3 meru_design.py --setup-from-source

# Step 2: Run baseline benchmarks
python3 meru_design.py postgres_setup/inst/bin Select1,RO_FullyCached

# Step 3: Run dynamic resize tests
cd ../perf_test_with_resize_restart
python3 collect_tps_and_resize.py \
    --bin-dir ../perf_test/postgres_setup/inst/bin \
    --result-dir ./results \
    --vcore 4

# Step 4: Visualize results
python3 plot_tps_latency_gaps.py -d results/data_*/

# Step 5: Analyze graphs and CSV files
ls -lh results/data_*/tps_latency_*.png
```

### Comparative Testing

```bash
# Test different core counts
for cores in 2 4 8 16; do
    python3 collect_tps_and_resize.py \
        --bin-dir /path/to/bin \
        --result-dir results_${cores}cores \
        --vcore $cores
done

# Compare results
for dir in results_*cores/data_*; do
    python3 plot_tps_latency_gaps.py -d "$dir"
done
```

## Output Files

### Standard Benchmarks (perf_test/)
- `performance_results.csv` - TPS, latency, throughput for each test case
- `progress_metrics.csv` - Real-time progress during test execution
- `warmup_output_*` - Warmup phase logs
- `progress_output_*` - Test execution logs

### Resize Tests (perf_test_with_resize_restart/)
- `tps_latency_logs.csv` - TPS and latency over time
- `cpu_usage_logs.csv` - CPU utilization
- `shared_buffer_sizes.csv` - Buffer configuration changes
- `restart_timings.csv` - Restart/resize event timings
- `tps_latency_*.png` - Performance graphs (4 variants per test case)

## Troubleshooting

### Common Issues

**PostgreSQL won't start:**
```bash
# Check logs
tail -f postgres_setup/test/log/postgresql.log

# Verify data directory
ls -la postgres_setup/test/

# Check port availability
netstat -tuln | grep 5432
```

**Python dependencies missing:**
```bash
pip install --upgrade psutil pandas matplotlib
```

**Permission errors:**
```bash
# Ensure write permissions
chmod -R 755 postgres_perf_file
```

**pgbench not found:**
```bash
# Verify bin directory
ls -la /path/to/postgres/bin/pgbench

# Add to PATH if needed
export PATH=/path/to/postgres/bin:$PATH
```

## Performance Tips

1. **For high-throughput testing:**
   - Use SSD storage for database
   - Increase system resources (RAM, CPU)
   - Tune PostgreSQL configuration (shared_buffers, work_mem)

2. **For accurate results:**
   - Run tests during low system activity
   - Use consistent hardware/environment
   - Allow adequate warmup time
   - Run multiple iterations

3. **For large-scale testing:**
   - Increase test duration for stability
   - Use larger scale factors
   - Monitor system resources (iostat, vmstat)

## Contributing

For issues or improvements:
1. Check existing documentation
2. Review troubleshooting sections
3. Verify prerequisites are met
4. Check PostgreSQL logs for errors

## Related Tools

- **pgbench** - PostgreSQL benchmarking tool (included with PostgreSQL)
- **matplotlib** - Graph generation and visualization
- **pandas** - Data analysis and CSV processing
- **psutil** - System resource monitoring

## License

This tool is part of the PostgreSQL performance analysis toolkit.

## Support

For detailed usage instructions, refer to the individual README files:
- Standard benchmarks: `perf_test/README.md`
- Resize testing: `perf_test_with_resize_restart/README.md`
