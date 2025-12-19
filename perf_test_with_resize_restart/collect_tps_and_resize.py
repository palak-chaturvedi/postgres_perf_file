#!/usr/bin/env python3
"""Comprehensive PostgreSQL performance data collector.

This tool orchestrates pgbench workloads, shared_buffers resizing, and a set of
continuously running monitors.  Metrics are streamed to CSV files inside
``/home/palak/perf/mod_data`` for downstream visualization.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import psutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOGGER = logging.getLogger("collect_data")


def parse_arguments():
    """Parse command line arguments.
    
    Usage: python collect_data.py [--bin-dir PATH] [--result-dir PATH] [--vcore N]
    
    Examples:
        python collect_data.py --bin-dir /home/user/postgres/inst/bin
        python collect_data.py --bin-dir /path/to/bin --result-dir /path/to/results --vcore 4
        python collect_data.py  # Interactive mode - prompts for inputs
    """
    parser = argparse.ArgumentParser(
        description="PostgreSQL Performance Data Collector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Specify bin directory
  python collect_data.py --bin-dir /home/user/postgres/inst/bin
  
  # Specify all parameters
  python collect_data.py --bin-dir /path/to/bin --result-dir /path/to/results --vcore 4
  
  # Interactive mode (prompts for inputs)
  python collect_data.py
        """
    )
    
    parser.add_argument(
        "--bin-dir",
        dest="bin_dir",
        type=str,
        help="Path to PostgreSQL bin directory (e.g., /home/user/postgres/inst/bin)"
    )
    
    parser.add_argument(
        "--result-dir",
        dest="result_dir",
        type=str,
        help="Path to store results (default: current directory)"
    )
    
    parser.add_argument(
        "--vcore",
        dest="vcore",
        type=int,
        help="Number of virtual cores (default: 2)"
    )
    
    args = parser.parse_args()
    
    # Interactive prompts for missing arguments
    if args.bin_dir is None:
        bin_dir_input = input("Please enter the PostgreSQL bin directory path (e.g., /home/user/postgres/inst/bin): ").strip()
        if not bin_dir_input:
            LOGGER.error("Bin directory is required")
            sys.exit(1)
        args.bin_dir = bin_dir_input
    
    if args.result_dir is None:
        result_dir_input = input(f"Please enter the result directory path (press Enter to use current directory: {os.getcwd()}): ").strip()
        args.result_dir = result_dir_input if result_dir_input else os.getcwd()
    
    if args.vcore is None:
        vcore_input = input("Please enter the number of virtual cores (press Enter to use default: 2): ").strip()
        args.vcore = int(vcore_input) if vcore_input else 2
    
    # Validate bin directory exists
    bin_path = Path(args.bin_dir)
    if not bin_path.exists():
        LOGGER.error(f"Bin directory does not exist: {args.bin_dir}")
        sys.exit(1)
    
    # Check for pgbench executable
    pgbench_path = bin_path / "pgbench"
    if not pgbench_path.exists():
        LOGGER.error(f"pgbench not found in {args.bin_dir}")
        sys.exit(1)
    
    # Create result directory if it doesn't exist
    result_path = Path(args.result_dir)
    result_path.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info("=" * 60)
    LOGGER.info("Configuration:")
    LOGGER.info(f"  PostgreSQL bin directory: {args.bin_dir}")
    LOGGER.info(f"  Result directory: {args.result_dir}")
    LOGGER.info(f"  Virtual cores: {args.vcore}")
    LOGGER.info("=" * 60)
    
    return args


@dataclass
class Config:
    # Command line arguments
    postgres_bin: Path
    result_base_dir: Path
    vcore: int
    
    # Connection settings
    host: str = "localhost"
    port: str = "5432"
    dbname: str = "testdb"
    maintenance_db: str = "postgres"
    
    # Test parameters
    scale: int = 128
    client_count: int = 128
    thread_count: int = 128
    duration: int = 3600  # 2hr per  test
    wait_between_changes: int = 600  # 20 minutes wait between changes
    restart_required: bool = False
    dynamic_resize: bool = True
    shared_buffer_sequence: Tuple[int, ...] = (4, 8, 12, 9, 4)
    
    # Derived paths
    data_dir: Optional[Path] = None
    collection_dir: Optional[Path] = None
    
    # Test configuration
    test_cases: Tuple[str, ...] = ("Select1","Select1NPPS","RO_Borderline","RO_FullyCached","RW_FullyCached")
    test_mode: str = "prepared"  # prepared, simple, or extended
    warmup_duration: int = 120  # 2 minutes warmup
    select1_file: str = "select1.sql"
    
    # Server configuration for CreatePGCommand
    client_multiplier: float = 2.0
    thread_multiplier: float = 1.0
    ro_fullcache_sf: float = 10.0
    ro_borderline_sf: float = 20.0
    rw_fullcache_sf: float = 5.0
    ro_fixed_sf: int = 100
    rw_fixed_sf: int = 50
    rw_test_duration: int = 300

    def __post_init__(self) -> None:
        # Derive data_dir from postgres_bin if not set
        if self.data_dir is None:
            # Assume data directory is ../test relative to bin
            self.data_dir = self.postgres_bin.parent.parent / "test"
        
        # Create collection directory with timestamp and parameters
        if self.collection_dir is None:
            timestamp = time.strftime('%Y-%m-%d_%H:%M')
            dir_name = f"data_{timestamp}_{self.scale}_{self.client_count}_{self.thread_count}_{self.duration}"
            self.collection_dir = self.result_base_dir / dir_name
        
        self.collection_dir.mkdir(parents=True, exist_ok=True)
        
        LOGGER.info(f"[Config] Data directory: {self.data_dir}")
        LOGGER.info(f"[Config] Collection directory: {self.collection_dir}")

    @property
    def shared_buffers_file(self) -> Path:
        return self.collection_dir / "shared_buffer_sizes.csv"

    @property
    def cpu_file(self) -> Path:
        return self.collection_dir / "cpu_usage_logs.csv"

    @property
    def tps_file(self) -> Path:
        return self.collection_dir / "tps_latency_logs.csv"

    @property
    def restart_file(self) -> Path:
        return self.collection_dir / "restart_timings.csv"

    @property
    def resize_file(self) -> Path:
        return self.collection_dir / "resize_timings.csv"
    
    def to_server_dict(self) -> dict:
        """Convert Config to server dictionary format for CreatePGCommand."""
        return {
            "pgserver_hosturl": self.host,
            "pgserver_dbport": self.port,
            "pgserver_dbname": self.dbname,
            "pgserver_testmode": self.test_mode,
            "pgserver_vcore": self.vcore,
            "pgserver_client_Multiplier": self.client_multiplier,
            "pgserver_thread_Multiplier": self.thread_multiplier,
            "pgserver_warmupduration": self.warmup_duration,
            "pgserver_testduration": self.duration,
            "pgserver_RW_testduration": self.rw_test_duration,
            "pgserver_RO_fullCacheSF": self.ro_fullcache_sf,
            "pgserver_RO_BorderLineSF": self.ro_borderline_sf,
            "pgserver_RW_fullcacheSF": self.rw_fullcache_sf,
            "pgserver_RO_FixedSF": self.ro_fixed_sf,
            "pgserver_RW_FixedSF": self.rw_fixed_sf,
        }


class CreatePGCommand:
    """Generate pgbench commands based on test case and server configuration."""
    
    @classmethod
    def pgcommand_to_execute(cls, server: dict, testcase: str, pgserver_select1file: str, bin_directory: str) -> dict:
        """Generate pgbench commands for initialization, warmup, and test runs."""
        warmup_required = False
        print(f"Creating commands for server: {server}")

        pgcommand_bin = f"{bin_directory}/pgbench"
        connection_params = " -h " + server["pgserver_hosturl"] + \
                           " -p " + server["pgserver_dbport"]
        pgbench_initialize = f"{pgcommand_bin} -i" + connection_params
        pgbench_common = f"{pgcommand_bin} -P 2" + \
            " -M " + server["pgserver_testmode"] + connection_params

        scale_factor, connections, threads = cls.calculate_scale_thread_connection(server, testcase)

        pgbenchcommand = pgbench_common + \
            " -c " + str(connections) + \
            " -j " + str(threads)

        if scale_factor:
            pgbenchcommand = pgbenchcommand + " -s " + str(scale_factor)
            pgbench_initialize = pgbench_initialize + " -s " + str(scale_factor)

        if "RO_" in testcase:
            pgbenchcommand = pgbenchcommand + " -S "
            warmup_required = True

        if "RW_" in testcase:
            pgbench_initialize = pgbench_initialize + " -F 90"
            warmup_required = True

        if "Select" in testcase:
            pgbenchcommand = pgbenchcommand + " -f " + pgserver_select1file

        if warmup_required:
            pgbenchwarmupcommand = pgbenchcommand + \
                " -T " + str(server["pgserver_warmupduration"])
            pgbenchwarmupcommand = pgbenchwarmupcommand + " " + server.get("pgserver_dbname", "testdb")

        if "RW_" in testcase:
            pgbenchcommand = pgbenchcommand + " -T " + str(server["pgserver_RW_testduration"])
        else:
            pgbenchcommand = pgbenchcommand + " -T " + str(server["pgserver_testduration"])

        pgbenchcommand = pgbenchcommand + " " + server.get("pgserver_dbname", "testdb")
        pgbench_initialize = pgbench_initialize + " " + server.get("pgserver_dbname", "testdb")

        pgbench_dict = {}
        pgbench_dict["initialize"] = pgbench_initialize
        if warmup_required:
            pgbench_dict["warmupruns"] = pgbenchwarmupcommand
        pgbench_dict["testruns"] = pgbenchcommand

        return pgbench_dict

    @classmethod
    def calculate_scale_thread_connection(cls, server: dict, testcase: str) -> Tuple[Optional[int], int, int]:
        """Calculate scale factor, thread & connection counts based on server cores."""
        v_cores = server["pgserver_vcore"]
        connections = int(server["pgserver_client_Multiplier"] * v_cores)
        threads = int(server["pgserver_thread_Multiplier"] * v_cores)

        if testcase == "Select1":
            return None, 1, 1
        if testcase == "Select1NPPS":
            return None, connections, threads
        if testcase == "RO_FullyCached":
            return cls.calculate_scalefactor(server["pgserver_RO_fullCacheSF"], v_cores), connections, threads
        if testcase == "RO_Borderline":
            return cls.calculate_scalefactor(server["pgserver_RO_BorderLineSF"], v_cores), connections, threads
        if testcase == "RW_FullyCached":
            return cls.calculate_scalefactor(server["pgserver_RW_fullcacheSF"], v_cores), connections, threads
        if testcase == "RO_FixedSF":
            return server["pgserver_RO_FixedSF"], connections, threads
        if testcase == "RW_FixedSF":
            return server["pgserver_RW_FixedSF"], connections, threads

        return None, connections, threads

    @classmethod
    def calculate_scalefactor(cls, sf_multiplier: float, v_cores: int) -> int:
        """Calculate scale factor using SF multiplier and vCores."""
        return int(sf_multiplier * v_cores / 2)


class CSVWriter:
    """Handles CSV file operations."""
    
    @staticmethod
    def write_line(path: Path, *values: object) -> None:
        """Write a line to CSV with timestamp."""
        try:
            with path.open("a", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow((time.strftime("%Y-%m-%d %H:%M:%S"), *values))
        except OSError as exc:
            LOGGER.error("[CSVWriter] Failed writing %s: %s", path, exc)


class DatabaseManager:
    """Manages PostgreSQL database operations."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def execute_sql(self, sql: str, timeout: int = 10, database: Optional[str] = None) -> Tuple[bool, str]:
        """Execute SQL and return (success, output)."""
        target_db = database or self.config.dbname
        cmd = [
            str(self.config.postgres_bin / "psql"),
            "-h", self.config.host,
            "-p", self.config.port,
            "-d", target_db,
            "-t", "-c", sql,
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "SQL timeout"
        except OSError as exc:
            return False, str(exc)

        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    
    def ensure_database(self) -> None:
        """Create a clean database and initialize pgbench."""
        LOGGER.info("[DatabaseManager] Preparing clean database '%s'", self.config.dbname)
        self.execute_sql(
            f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{self.config.dbname}'",
            database=self.config.maintenance_db,
        )
        self.execute_sql(f"DROP DATABASE IF EXISTS {self.config.dbname}", database=self.config.maintenance_db)
        success, result = self.execute_sql(
            f"CREATE DATABASE {self.config.dbname}", database=self.config.maintenance_db
        )
        if not success:
            raise RuntimeError(f"Failed to create database: {result}")

        init_cmd = [
            str(self.config.postgres_bin / "pgbench"),
            "-h", self.config.host, "-p", self.config.port,
         "-i", "-s", str(self.config.scale),
            self.config.dbname,
        ]
        LOGGER.info("[DatabaseManager] Initializing pgbench (scale=%s)", self.config.scale)
        result = subprocess.run(
            init_cmd, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pgbench init failed: {result.stderr.strip()}")
    
    def cleanup_database(self) -> None:
        """Drop the test database."""
        LOGGER.info("[DatabaseManager] Dropping database '%s'", self.config.dbname)
        self.execute_sql(f"DROP DATABASE IF EXISTS {self.config.dbname}", database=self.config.maintenance_db)
    
    def postgres_is_running(self) -> bool:
        """Check if PostgreSQL is running."""
        return any(proc.info.get("name") == "postgres" for proc in psutil.process_iter(["name"]))


class MonitoringManager:
    """Manages system monitoring threads."""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
    
    def shared_buffers_monitor(self, stop_event: threading.Event) -> None:
        """Monitor shared_buffers configuration."""
        LOGGER.info("[MonitoringManager] Shared buffers monitor started")
        while not stop_event.is_set():
            success, raw = self.db_manager.execute_sql("SHOW shared_buffers;")
            if success and raw:
                token = raw.split()[0]
                try:
                    CSVWriter.write_line(
                        self.config.shared_buffers_file,
                        int(float(token.replace("GB", ""))),
                    )
                except ValueError:
                    LOGGER.debug("[MonitoringManager] Unexpected SHOW shared_buffers output: %s", raw)
            stop_event.wait(1)
        LOGGER.info("[MonitoringManager] Shared buffers monitor stopped")
    
    def cpu_monitor(self, stop_event: threading.Event) -> None:
        """Monitor CPU usage."""
        LOGGER.info("[MonitoringManager] CPU monitor started")
        while not stop_event.is_set():
            cpu_percent = psutil.cpu_percent(interval=1)
            CSVWriter.write_line(self.config.cpu_file, cpu_percent)
            stop_event.wait(1)
        LOGGER.info("[MonitoringManager] CPU monitor stopped")


class BenchmarkRunner:
    """Manages pgbench benchmark execution."""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
    
    def _execute_pgbench_command(self, command: str, run_type: str, test_case: str, stop_event: threading.Event) -> None:
        """Execute a pgbench command and log progress."""
        LOGGER.info("[BenchmarkRunner] Executing %s for %s: %s", run_type, test_case, command)
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        print("outpt", process.stdout.readline())


        try:
            while not stop_event.is_set():
                line = process.stderr.readline()
                if not line:
                    break
                if line.strip():
                    LOGGER.debug("[BenchmarkRunner] %s output: %s", run_type, line.strip())
                
                if "progress:" not in line:
                    continue
                    
                try:
                    match = re.search(
                        r'progress: ([\d.]+) s, ([\d.]+) tps, lat ([\d.]+) ms stddev ([\d.]+)',
                        line
                    )
                    if match:
                        elapsed = float(match.group(1))
                        tps = float(match.group(2))
                        latency_avg = float(match.group(3))
                        latency_stddev = float(match.group(4))
                        
                        LOGGER.info(
                            "[BenchmarkRunner] %s [%s] @ %.1fs: TPS=%.2f, Latency=%.2fms (stddev=%.2fms)",
                            test_case, run_type, elapsed, tps, latency_avg, latency_stddev
                        )
                        CSVWriter.write_line(
                            self.config.tps_file, 
                            test_case, run_type, elapsed, tps, latency_avg, latency_stddev
                        )
                except (IndexError, ValueError, AttributeError) as exc:
                    LOGGER.debug("[BenchmarkRunner] Failed to parse output '%s': %s", line.strip(), exc)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
    
    def run_test_cases(self, test_case, stop_event: threading.Event) -> None:
        """Run benchmark continuously for all buffer changes."""
        LOGGER.info("[BenchmarkRunner] Starting continuous test execution for: %s", test_case)
        
        server_dict = self.config.to_server_dict()
        bin_directory = str(self.config.postgres_bin)
        select1_file = self.config.select1_file
        
        LOGGER.info("[BenchmarkRunner] " + "="*60)
        LOGGER.info("[BenchmarkRunner] Starting test case: %s", test_case)
        LOGGER.info("[BenchmarkRunner] " + "="*60)
        
        try:
            pgcommands = CreatePGCommand.pgcommand_to_execute(
                server_dict, test_case, select1_file, bin_directory
            )
        except Exception as exc:
            LOGGER.error("[BenchmarkRunner] Failed to generate commands for %s: %s", test_case, exc)
            return

        print("PG Commands to be executed:", pgcommands)
        
        # Initialize database once at start
        if "initialize" in pgcommands:
            LOGGER.info("[BenchmarkRunner] Initializing database for %s", test_case)
            try:
                result = subprocess.run(
                    pgcommands["initialize"],
                    shell=True,
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    LOGGER.error("[BenchmarkRunner] Initialization failed: %s", result.stderr)
                    return
                LOGGER.info("[BenchmarkRunner] Database initialization completed")
            except Exception as exc:
                LOGGER.error("[BenchmarkRunner] Initialization error: %s", exc)
                return
        
        # Run warmup once at start
        if "warmupruns" in pgcommands and not stop_event.is_set():
            LOGGER.info("[BenchmarkRunner] Running initial warmup for %s", test_case)
            self._execute_pgbench_command(
                pgcommands["warmupruns"], "warmup", test_case, stop_event
            )
            LOGGER.info("[BenchmarkRunner] Initial warmup completed for %s", test_case)
            stop_event.wait(5)
        
        # Run measurement continuously until stop_event is set
        run_count = 0
        while not stop_event.is_set():
            run_count += 1
            if "testruns" in pgcommands:
                LOGGER.info("[BenchmarkRunner] Running measurement #%d for %s", run_count, test_case)
                self._execute_pgbench_command(
                    pgcommands["testruns"], "measurement", test_case, stop_event
                )
                if not stop_event.is_set():
                    LOGGER.info("[BenchmarkRunner] Measurement #%d completed for %s", run_count, test_case)
                    # Short pause between runs
                    stop_event.wait(2)
        
        LOGGER.info("[BenchmarkRunner] Test case %s completed after %d runs", test_case, run_count)


class ResizeController:
    """Manages shared_buffers resize operations."""
    
    def __init__(self, config: Config, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
    
    def _record_restart_event(self, status: str, size_gb: int, testcase: str) -> None:
        """Record restart event to CSV."""
        CSVWriter.write_line(self.config.restart_file, status, f"{size_gb}GB", testcase)
    
    def _record_resize_event(self, status: str, size_gb: int, testcase: str) -> None:
        """Record resize event to CSV."""
        CSVWriter.write_line(self.config.resize_file, status, f"{size_gb}GB", testcase)
    
    def resize_controller(self, testcase, stop_event: threading.Event) -> None:
        """Control shared_buffers resizing through configured sequence."""
        LOGGER.info("[ResizeController] Shared_buffers controller sequence: %s", self.config.shared_buffer_sequence)
        for index, size in enumerate(self.config.shared_buffer_sequence, start=1):
            if stop_event.is_set():
                break
            if index > 1 and stop_event.wait(self.config.wait_between_changes):
                break

            LOGGER.info(
                "[ResizeController] [Step %s/%s] Setting shared_buffers=%sGB",
                index, len(self.config.shared_buffer_sequence), size,
            )
            sql_command = f"ALTER SYSTEM SET shared_buffers = '{size}GB'"
            success, result = self.db_manager.execute_sql(sql_command)
            if not success:
                LOGGER.error("[ResizeController] Failed to set shared_buffers: %s", result)
                return

            reload_success, reload_msg = self.db_manager.execute_sql("SELECT pg_reload_conf();")
            if reload_success:
                LOGGER.info("[ResizeController] Configuration reload successful")
            else:
                LOGGER.warning("[ResizeController] Configuration reload failed: %s", reload_msg)

            if self.config.dynamic_resize:
                self._record_resize_event("Started", size, testcase)
                resize_success, resize_result = self.db_manager.execute_sql(
                    "SELECT pg_resize_shared_buffers();", timeout=600,
                )
                while (
                    resize_success
                    and resize_result.strip() != "t"
                    and not stop_event.wait(5)
                ):
                    LOGGER.info(
                        "[ResizeController] Waiting for pg_resize_shared_buffers(); current result=%s",
                        resize_result,
                    )
                    resize_success, resize_result = self.db_manager.execute_sql(
                        "SELECT pg_resize_shared_buffers();", timeout=600,
                    )
                self._record_resize_event("Completed", size,testcase)

            print("Self.config.restart_required is set to:", self.config.restart_required)
            if self.config.restart_required:
                print("DOING RESTART FOR SHARED_BUFFERS CHANGE")
                self._record_restart_event("Started", size, testcase)
                restart_cmd = [
                    str(self.config.postgres_bin / "pg_ctl"),
                    "-D", str(self.config.data_dir),
                    "restart", "-l", "logfile",
                ]

                print("restarting the server, command is:", restart_cmd)

                result = subprocess.run(restart_cmd, capture_output=True, text=True)
                print("restart command output:", result.stdout)
                if result.returncode != 0:
                    LOGGER.error("[ResizeController] pg_ctl restart failed: %s", result.stderr.strip())
                else:
                    LOGGER.debug("[ResizeController] pg_ctl stdout: %s", result.stdout.strip())

                start_cmd = [
                    str(self.config.postgres_bin / "pg_ctl"),
                    "-D", str(self.config.data_dir),
                    "start", "-l logfile",
                ]

                while not self.db_manager.postgres_is_running() and not stop_event.wait(1):
                    LOGGER.debug("[ResizeController] Waiting for postgres processes to return...")
                    time.sleep(2)
                    result = subprocess.run(start_cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        LOGGER.error("[ResizeController] pg_ctl start failed: %s", result.stderr.strip())
                    else:
                        LOGGER.debug("[ResizeController] pg_ctl stdout: %s", result.stdout.strip())
                self._record_restart_event("Completed", size, testcase)
                stop_event.wait(5)

            success, current_value = self.db_manager.execute_sql("SHOW shared_buffers;")
            if success:
                LOGGER.info("[ResizeController] Current shared_buffers: %s", current_value.strip())

        LOGGER.info("[ResizeController] Shared_buffers controller finished")


class PerformanceCollector:
    """Main orchestrator for performance data collection."""
    
    def __init__(self, config: Config):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.monitoring_manager = MonitoringManager(config, self.db_manager)
        self.benchmark_runner = BenchmarkRunner(config, self.db_manager)
        self.resize_controller = ResizeController(config, self.db_manager)
    
    def run(self) -> None:
        """Run the performance collection process."""

        for testcase in self.config.test_cases:
            LOGGER.info(f"[PerformanceCollector] Starting PostgreSQL performance monitoring for test case {testcase}")
            stop_event = threading.Event()

            try:
                self.db_manager.ensure_database()
            except RuntimeError as exc:
                LOGGER.error("[PerformanceCollector] Setup failed: %s", exc)
                return

            controller_thread = threading.Thread(
                target=self.resize_controller.resize_controller,
                args=(testcase,stop_event,),
                daemon=True,
            )
            controller_thread.start()

            time.sleep(5)
            workers = [
                # threading.Thread(target=self.monitoring_manager.cpu_monitor, args=(stop_event,), daemon=True),
                # threading.Thread(target=self.monitoring_manager.shared_buffers_monitor, args=(stop_event,), daemon=True),
                threading.Thread(target=self.benchmark_runner.run_test_cases, args=(testcase,stop_event,), daemon=True),
            ]
            for worker in workers:
                worker.start()



            try:
                controller_thread.join()
            except KeyboardInterrupt:
                LOGGER.info("[PerformanceCollector] Ctrl+C received, stopping background threads")
            finally:
                LOGGER.info("[PerformanceCollector] Resize controller finished, waiting for last test to complete...")
                for worker in workers:
                    worker.join(timeout=self.config.duration)
                stop_event.set()
                for worker in workers:
                    worker.join(timeout=2)
                self.db_manager.cleanup_database()
                LOGGER.info("[PerformanceCollector] Shutdown complete")


def main() -> None:
    """Entry point for the performance collector."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Create configuration with parsed arguments
    config = Config(
        postgres_bin=Path(args.bin_dir),
        result_base_dir=Path(args.result_dir),
        vcore=args.vcore
    )
    
    # Run performance collection
    collector = PerformanceCollector(config)
    collector.run()

if __name__ == "__main__":
    main()
