"""
Linux Process Manager for Hyperliquid Auto-Trade Services

This script manages all the services needed for the Hyperliquid auto-trade application:
1. WebSocket Discovery Service
2. Celery Worker
3. Celery Beat Scheduler
4. FastAPI Web Server
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/process_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ProcessManager')

class ProcessManager:
    """Process manager for Linux to handle all Hyperliquid services"""
    
    def __init__(self):
        self.services = {}
        self.running = True
        self.project_root = Path(__file__).parent
        self.logs_dir = self.project_root / "logs"
        
        # Ensure logs directory exists
        self.logs_dir.mkdir(exist_ok=True)
        
        # Define services in startup order
        self.service_configs = {
            'websocket-discovery': {
                'command': [sys.executable, 'start_discovery_service.py'],
                'priority': 1,
                'restart_delay': 5,
                'description': 'WebSocket Discovery Service'
            },
            'celery-worker': {
                'command': [
                    sys.executable, '-m', 'celery', '-A', 'app.services.celery_app', 
                    'worker', '--loglevel=info', '--concurrency=4'
                ],
                'priority': 2,
                'restart_delay': 10,
                'description': 'Celery Worker'
            },
            'celery-beat': {
                'command': [
                    sys.executable, '-m', 'celery', '-A', 'app.services.celery_app', 
                    'beat', '--loglevel=info'
                ],
                'priority': 3,
                'restart_delay': 15,
                'description': 'Celery Beat Scheduler',
                'depends_on': ['celery-worker']
            },
            'fastapi-server': {
                'command': [sys.executable, 'run.py'],
                'priority': 4,
                'restart_delay': 5,
                'description': 'FastAPI Web Server'
            }
        }
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down all services...")
        self.running = False
        self.stop_all_services()
    
    def start_service(self, service_name, config):
        """Start a single service"""
        if service_name in self.services:
            logger.warning(f"Service {service_name} is already running")
            return
        
        # Check dependencies
        if 'depends_on' in config:
            for dep in config['depends_on']:
                if dep not in self.services or not self.is_service_running(dep):
                    logger.warning(f"Cannot start {service_name}: dependency {dep} is not running")
                    return
        
        try:
            log_file = self.logs_dir / f"{service_name}.log"
            error_file = self.logs_dir / f"{service_name}.error.log"
            
            # Open log files
            stdout_file = open(log_file, 'a')
            stderr_file = open(error_file, 'a')
            
            # Write startup header
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            stdout_file.write(f"\n{'='*60}\n")
            stdout_file.write(f"Service {service_name} started at {timestamp}\n")
            stdout_file.write(f"Command: {' '.join(config['command'])}\n")
            stdout_file.write(f"{'='*60}\n\n")
            stdout_file.flush()
            
            # Start the process
            process = subprocess.Popen(
                config['command'],
                cwd=self.project_root,
                stdout=stdout_file,
                stderr=stderr_file,
                preexec_fn=os.setsid  # Create new process group for clean shutdown
            )
            
            self.services[service_name] = {
                'process': process,
                'config': config,
                'stdout_file': stdout_file,
                'stderr_file': stderr_file,
                'start_time': datetime.now(),
                'restart_count': 0
            }
            
            logger.info(f"✅ Started {config['description']} (PID: {process.pid})")
            
        except Exception as e:
            logger.error(f"❌ Failed to start {service_name}: {e}")
            # Clean up file handles if they were opened
            try:
                stdout_file.close()
                stderr_file.close()
            except:
                pass
    
    def stop_service(self, service_name):
        """Stop a single service"""
        if service_name not in self.services:
            logger.warning(f"Service {service_name} is not running")
            return
        
        service = self.services[service_name]
        process = service['process']
        
        try:
            logger.info(f"🛑 Stopping {service['config']['description']}...")
            
            # Send SIGTERM to the process group
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                # Process already terminated
                pass
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
                logger.info(f"✅ {service_name} stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                logger.warning(f"⚡ Force killing {service_name}")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
            
            # Close log files
            service['stdout_file'].close()
            service['stderr_file'].close()
            
            del self.services[service_name]
            
        except Exception as e:
            logger.error(f"❌ Error stopping {service_name}: {e}")
    
    def is_service_running(self, service_name):
        """Check if a service is running"""
        if service_name not in self.services:
            return False
        
        process = self.services[service_name]['process']
        return process.poll() is None
    
    def restart_service(self, service_name):
        """Restart a service"""
        if service_name in self.services:
            config = self.services[service_name]['config']
            self.stop_service(service_name)
            time.sleep(2)  # Brief pause before restart
            self.start_service(service_name, config)
    
    def start_all_services(self):
        """Start all services in priority order"""
        logger.info("🚀 Starting all Hyperliquid services...")
        
        # Sort services by priority
        sorted_services = sorted(
            self.service_configs.items(),
            key=lambda x: x[1]['priority']
        )
        
        for service_name, config in sorted_services:
            if not self.running:
                break
                
            logger.info(f"Starting {config['description']}...")
            self.start_service(service_name, config)
            
            # Wait a bit between service starts
            time.sleep(config.get('restart_delay', 5))
        
        logger.info("✅ All services started!")
    
    def stop_all_services(self):
        """Stop all services in reverse priority order"""
        logger.info("🛑 Stopping all services...")
        
        # Sort services by reverse priority
        sorted_services = sorted(
            [(name, self.services[name]['config']) for name in self.services.keys()],
            key=lambda x: x[1]['priority'],
            reverse=True
        )
        
        for service_name, config in sorted_services:
            self.stop_service(service_name)
            time.sleep(1)  # Brief pause between stops
        
        logger.info("✅ All services stopped!")
    
    def monitor_services(self):
        """Monitor services and restart if they crash"""
        logger.info("👁️ Starting service monitoring...")
        
        while self.running:
            try:
                for service_name in list(self.services.keys()):
                    if not self.is_service_running(service_name):
                        service = self.services[service_name]
                        service['restart_count'] += 1
                        
                        logger.warning(f"💀 {service_name} crashed! Restart count: {service['restart_count']}")
                        
                        # Limit restart attempts
                        if service['restart_count'] <= 5:
                            logger.info(f"🔄 Restarting {service_name}...")
                            self.restart_service(service_name)
                        else:
                            logger.error(f"❌ {service_name} has crashed too many times, not restarting")
                            self.stop_service(service_name)
                
                time.sleep(10)  # Check every 10 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in service monitoring: {e}")
                time.sleep(5)
    
    def print_status(self):
        """Print status of all services"""
        print("\n" + "="*60)
        print("HYPERLIQUID AUTO-TRADE SERVICE STATUS")
        print("="*60)
        
        if not self.services:
            print("No services running")
            return
        
        for service_name, service in self.services.items():
            status = "🟢 RUNNING" if self.is_service_running(service_name) else "🔴 STOPPED"
            uptime = datetime.now() - service['start_time']
            pid = service['process'].pid
            restarts = service['restart_count']
            
            print(f"{service['config']['description']:<25} {status}")
            print(f"  └─ PID: {pid}, Uptime: {uptime}, Restarts: {restarts}")
        
        print("="*60)
    
    def run(self):
        """Main run method"""
        self.setup_signal_handlers()
        
        try:
            # Start all services
            self.start_all_services()
            
            # Start monitoring in a separate thread
            monitor_thread = threading.Thread(target=self.monitor_services, daemon=True)
            monitor_thread.start()
            
            # Main loop
            while self.running:
                try:
                    time.sleep(30)  # Print status every 30 seconds
                    if self.running:
                        self.print_status()
                except KeyboardInterrupt:
                    break
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            self.stop_all_services()


def main():
    """Main entry point"""
    print("🚀 Hyperliquid Auto-Trade Process Manager")
    print("==========================================")
    
    manager = ProcessManager()
    manager.run()


if __name__ == "__main__":
    main()
