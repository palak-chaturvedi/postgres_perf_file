#!/usr/bin/env python3
"""
PostgreSQL Online Shared Buffers Resize Performance Analysis
Multi-threaded performance testing with dynamic shared_buffers changes
"""

import subprocess
import threading
import time
import datetime
import csv
import os
import re
import psutil
import queue
import signal
import sys
from typing import Dict, List, Optional, Tuple

class PostgreSQLPerformanceAnalyzer:
    def __init__(self):
        self.postgres_bin = "/home/palak/og_postgres/inst/bin"
        self.data_dir = "/home/palak/og_postgres/test"
        self.host = "localhost"
        self.port = "5432"
        self.username = "palak"
        self.password = "password123"
        self.dbname = "testdb"
        
        # Threading control
        self.stop_monitoring = False
        self.pgbench_process = None
        self.current_pgbench_thread = None
        
        # Data collection
        self.performance_data = queue.Queue()
        self.csv_filename = f"dynamic_resize_performance_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Shared buffers resize sequence
        self.resize_sequence = ["8GB", "16GB", "4GB", "12GB"]
        self.resize_interval = 30  # seconds
        
        print(f"🔧 Initializing PostgreSQL Performance Analyzer")
        print(f"📊 Results will be saved to: {self.csv_filename}")
    
    def execute_sql(self, sql: str, timeout: int = 10) -> Tuple[bool, str]:
        """Execute SQL command and return success status and result"""
        try:
            cmd = f"""PGPASSWORD={self.password} {self.postgres_bin}/psql \
                -h {self.host} -p {self.port} -U {self.username} -d {self.dbname} \
                -t -c "{sql}" """
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
                
        except subprocess.TimeoutExpired:
            return False, "SQL timeout"
        except Exception as e:
            return False, str(e)
    
    def initialize_database(self) -> bool:
        """Initialize pgbench database with scale factor 240"""
        print("🔄 Initializing pgbench database (scale=240)...")
        
        try:
            # Drop existing database and recreate
            drop_cmd = f"PGPASSWORD={self.password} {self.postgres_bin}/dropdb --if-exists -h {self.host} -p {self.port} -U {self.username} {self.dbname}"
            subprocess.run(drop_cmd, shell=True, capture_output=True)
            
            create_cmd = f"PGPASSWORD={self.password} {self.postgres_bin}/createdb -h {self.host} -p {self.port} -U {self.username} {self.dbname}"
            result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ Database creation failed: {result.stderr}")
                return False
            
            # Initialize with pgbench
            init_cmd = f"PGPASSWORD={self.password} {self.postgres_bin}/pgbench  -h {self.host} -p {self.port} -U {self.username} -i -s 1 {self.dbname}"
            result = subprocess.run(init_cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Database initialized successfully")
                return True
            else:
                print(f"❌ Database initialization failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            return False
    
    def run_pgbench_test(self) -> None:
        """Run pgbench test and collect TPS/Latency data"""
        print("🚀 Starting pgbench performance test...")
        
        try:
            cmd = f"""PGPASSWORD={self.password} {self.postgres_bin}/pgbench \
                -P 1 -M prepared -h {self.host} -p {self.port} -U {self.username} \
                -c 128 -j 128 -s 240 -T 180 {self.dbname}"""
            
            self.pgbench_process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                text=True, bufsize=1, universal_newlines=True
            )
            
            # Parse pgbench output in real-time
            for line in iter(self.pgbench_process.stdout.readline, ''):
                print(line)
                if self.stop_monitoring:
                    break
                
                # Parse progress report lines
                if 'progress:' in line:
                    timestamp = datetime.datetime.now()
                    tps, latency = self.parse_pgbench_line(line)
                    
                    if tps and latency:
                        data_point = {
                            'timestamp': timestamp,
                            'tps': tps,
                            'latency_avg': latency,
                            'data_type': 'pgbench'
                        }
                        self.performance_data.put(data_point)
            
            self.pgbench_process.wait()
            
        except Exception as e:
            print(f"❌ PGBench test error: {e}")
        
        print("⏹️ PGBench test completed")
    
    def parse_pgbench_line(self, line: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse TPS and latency from pgbench progress line"""
        try:
            # Example: progress: 10.0 s, 30234.5 tps, lat 4.123 ms stddev 1.456
            tps_match = re.search(r'(\d+\.?\d*)\s+tps', line)
            lat_match = re.search(r'lat\s+(\d+\.?\d*)\s+ms', line)
            
            tps = float(tps_match.group(1)) if tps_match else None
            latency = float(lat_match.group(1)) if lat_match else None
            
            return tps, latency
            
        except Exception as e:
            return None, None
    
    def monitor_system_metrics(self) -> None:
        """Monitor system performance metrics"""
        print("📊 Starting system metrics monitoring...")
        
        while not self.stop_monitoring:
            try:
                timestamp = datetime.datetime.now()
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                
                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_used_mb = memory.used / 1024 / 1024
                memory_available_mb = memory.available / 1024 / 1024
                
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                disk_read_mb_s = disk_io.read_bytes / 1024 / 1024 if disk_io else 0
                disk_write_mb_s = disk_io.write_bytes / 1024 / 1024 if disk_io else 0
                
                # Network I/O
                network_io = psutil.net_io_counters()
                network_sent_mb_s = network_io.bytes_sent / 1024 / 1024 if network_io else 0
                network_recv_mb_s = network_io.bytes_recv / 1024 / 1024 if network_io else 0
                
                # Load average
                load_avg = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
                
                # PostgreSQL process metrics
                postgres_cpu, postgres_memory_mb = self.get_postgres_metrics()
                
                data_point = {
                    'timestamp': timestamp,
                    'cpu_usage_percent': cpu_percent,
                    'memory_usage_percent': memory_percent,
                    'memory_used_mb': memory_used_mb,
                    'memory_available_mb': memory_available_mb,
                    'disk_read_mb_s': disk_read_mb_s,
                    'disk_write_mb_s': disk_write_mb_s,
                    'network_sent_mb_s': network_sent_mb_s,
                    'network_recv_mb_s': network_recv_mb_s,
                    'load_average': load_avg,
                    'postgres_cpu_percent': postgres_cpu,
                    'postgres_memory_mb': postgres_memory_mb,
                    'data_type': 'system_metrics'
                }
                
                self.performance_data.put(data_point)
                
            except Exception as e:
                print(f"⚠️ System metrics error: {e}")
            
            time.sleep(1)  # Collect every second
        
        print("⏹️ System metrics monitoring stopped")
    
    def get_postgres_metrics(self) -> Tuple[float, float]:
        """Get PostgreSQL process-specific CPU and memory usage"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
                if 'postgres' in proc.info['name'].lower():
                    cpu_percent = proc.info['cpu_percent'] or 0
                    memory_mb = (proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0
                    return cpu_percent, memory_mb
            return 0, 0
        except Exception:
            return 0, 0
    
    def monitor_shared_buffers(self) -> None:
        """Monitor shared_buffers value every second"""
        print("🔍 Starting shared_buffers monitoring...")
        
        while not self.stop_monitoring:
            try:
                success, shared_buffers = self.execute_sql("SHOW shared_buffers", timeout=5)
                
                if success:
                    timestamp = datetime.datetime.now()
                    data_point = {
                        'timestamp': timestamp,
                        'shared_buffers': shared_buffers.strip(),
                        'data_type': 'shared_buffers'
                    }
                    self.performance_data.put(data_point)
                
            except Exception as e:
                print(f"⚠️ Shared buffers monitoring error: {e}")
            
            time.sleep(1)
        
        print("⏹️ Shared buffers monitoring stopped")
    
    def dynamic_resize_controller(self) -> None:
        """Control shared_buffers resizing at intervals"""
        print("🔄 Starting dynamic shared_buffers resize controller...")
        
        resize_index = 0
        
        # Wait initial 30 seconds before first resize
        for i in range(30):
            if self.stop_monitoring:
                return
            time.sleep(1)
        
        while not self.stop_monitoring and resize_index < len(self.resize_sequence):
            new_size = self.resize_sequence[resize_index]
            print(f"\n⚡ Initiating resize to {new_size} (step {resize_index + 1}/{len(self.resize_sequence)})")
            
            success = self.resize_shared_buffers(new_size)
            
            # Log the resize event
            timestamp = datetime.datetime.now()
            data_point = {
                'timestamp': timestamp,
                'resize_target': new_size,
                'resize_success': success,
                'resize_step': resize_index + 1,
                'data_type': 'resize_event'
            }
            self.performance_data.put(data_point)
            
            resize_index += 1
            
            # Wait for next resize interval
            for i in range(self.resize_interval):
                if self.stop_monitoring:
                    return
                time.sleep(1)
        
        print("🏁 Dynamic resize sequence completed")
    
    def resize_shared_buffers(self, new_size: str) -> bool:
        """Resize shared_buffers using ALTER SYSTEM and reload"""
        try:
            print(f"  📝 Setting shared_buffers to {new_size}...")
            
            # Step 1: ALTER SYSTEM SET shared_buffers
            alter_sql = f"ALTER SYSTEM SET shared_buffers = '{new_size}'"
            success, result = self.execute_sql(alter_sql)
            
            if not success:
                print(f"  ❌ ALTER SYSTEM failed: {result}")
                return False
            
            print("  ✅ ALTER SYSTEM completed")
            
            # Step 2: Reload configuration
            print("  🔄 Reloading configuration...")
            success, result = self.execute_sql("SELECT pg_reload_conf()")
            
            if not success:
                print(f"  ❌ Configuration reload failed: {result}")
                return False
            
            print("  ✅ Configuration reloaded")
            
            # Step 3: Restart PostgreSQL node
            print("  🔄 Restarting PostgreSQL...")
            restart_success = self.restart_postgresql()
            
            if not restart_success:
                print("  ❌ PostgreSQL restart failed")
                return False
            
            print("  ✅ PostgreSQL restarted")
            
            # Step 4: Restart pgbench if needed
            print("  🔄 Restarting pgbench test...")
            self.restart_pgbench_test()
            
            # Verify the change
            time.sleep(2)
            success, current_value = self.execute_sql("SHOW shared_buffers")
            if success:
                print(f"  ✅ Verified: shared_buffers = {current_value.strip()}")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Resize error: {e}")
            return False
    
    def restart_postgresql(self) -> bool:
        """Restart PostgreSQL server"""
        try:
            restart_cmd = f"{self.postgres_bin}/pg_ctl -D {self.data_dir} restart -l logfile"
            print(restart_cmd)
            result = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)
            time.sleep(20)
            if result.returncode == 0:
                time.sleep(5)  # Wait for startup
                return True
            else:
                print(f"Restart error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Restart exception: {e}")
            return False
    
    def restart_pgbench_test(self) -> None:
        """Restart pgbench test after PostgreSQL restart"""
        try:
            # Stop current pgbench if running
            if self.pgbench_process and self.pgbench_process.poll() is None:
                self.pgbench_process.terminate()
                self.pgbench_process.wait()
            
            # Start new pgbench thread
            if self.current_pgbench_thread and self.current_pgbench_thread.is_alive():
                # Let the current thread finish naturally
                pass
            
            self.current_pgbench_thread = threading.Thread(target=self.run_pgbench_test, daemon=True)
            self.current_pgbench_thread.start()
            
        except Exception as e:
            print(f"PGBench restart error: {e}")
    
    def save_performance_data(self) -> None:
        """Save collected performance data to CSV"""
        print("💾 Saving performance data to CSV...")
        
        # Collect all data from queue
        all_data = []
        while not self.performance_data.empty():
            try:
                data_point = self.performance_data.get_nowait()
                all_data.append(data_point)
            except queue.Empty:
                break
        
        if not all_data:
            print("⚠️ No data to save")
            return
        
        # Define CSV columns
        fieldnames = [
            'timestamp', 'data_type', 'tps', 'latency_avg', 'shared_buffers',
            'cpu_usage_percent', 'memory_usage_percent', 'memory_used_mb', 'memory_available_mb',
            'disk_read_mb_s', 'disk_write_mb_s', 'network_sent_mb_s', 'network_recv_mb_s',
            'load_average', 'postgres_cpu_percent', 'postgres_memory_mb',
            'resize_target', 'resize_success', 'resize_step'
        ]
        
        try:
            with open(self.csv_filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for data_point in all_data:
                    # Ensure all fields exist
                    row = {field: data_point.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"✅ Data saved to {self.csv_filename} ({len(all_data)} records)")
            
        except Exception as e:
            print(f"❌ Error saving data: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n🛑 Received signal {signum}, stopping analysis...")
        self.stop_monitoring = True
        
        if self.pgbench_process and self.pgbench_process.poll() is None:
            self.pgbench_process.terminate()
        
        # Save data before exit
        self.save_performance_data()
        sys.exit(0)
    
    def run_analysis(self) -> None:
        """Run the complete performance analysis"""
        print("🚀 STARTING POSTGRESQL ONLINE RESIZE PERFORMANCE ANALYSIS")
        print("=" * 80)
        
        # Set up signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        try:
            # Step 1: Initialize database
            if not self.initialize_database():
                print("❌ Failed to initialize database")
                return
            
            print(f"\n📋 Test Configuration:")
            print(f"   Duration: 600 seconds (10 minutes)")
            print(f"   Resize Sequence: {' -> '.join(self.resize_sequence)}")
            print(f"   Resize Interval: {self.resize_interval} seconds")
            print(f"   Clients: 128, Threads: 128")
            print(f"   Scale Factor: 240")
            
            # Step 2: Start monitoring threads
            threads = []
            
            # System metrics monitoring
            system_thread = threading.Thread(target=self.monitor_system_metrics, daemon=True)
            threads.append(system_thread)
            system_thread.start()
            
            # Shared buffers monitoring
            buffers_thread = threading.Thread(target=self.monitor_shared_buffers, daemon=True)
            threads.append(buffers_thread)
            buffers_thread.start()
            
            # Dynamic resize controller
            resize_thread = threading.Thread(target=self.dynamic_resize_controller, daemon=True)
            threads.append(resize_thread)
            resize_thread.start()
            
            # Step 3: Start pgbench test
            pgbench_thread = threading.Thread(target=self.run_pgbench_test, daemon=True)
            threads.append(pgbench_thread)
            self.current_pgbench_thread = pgbench_thread
            pgbench_thread.start()
            
            print(f"\n🎯 All monitoring threads started!")
            print(f"📊 Real-time data collection in progress...")
            print(f"⏰ Test will run for 10 minutes with resize sequence")
            print(f"🔄 Press Ctrl+C to stop early and save results")
            
            # Wait for test completion (600 seconds + buffer)
            time.sleep(620)
            
        except Exception as e:
            print(f"❌ Analysis error: {e}")
        
        finally:
            # Stop all monitoring
            print(f"\n⏹️ Stopping analysis...")
            self.stop_monitoring = True
            
            # Terminate pgbench
            if self.pgbench_process and self.pgbench_process.poll() is None:
                self.pgbench_process.terminate()
            
            # Wait for threads to finish
            time.sleep(3)
            
            # Save final results
            self.save_performance_data()
            
            print(f"\n🎉 Analysis completed!")
            print(f"📁 Results saved to: {self.csv_filename}")
            print(f"📊 Use performance analysis tools to examine the impact of dynamic resizing")


def main():
    """Main function to run the analysis"""
    analyzer = PostgreSQLPerformanceAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()