"""
Service Control Script for Hyperliquid Auto-Trade

This script provides commands to control individual services:
- start <service>
- stop <service>  
- restart <service>
- status
- logs <service>
"""

import sys
import subprocess
import argparse
from pathlib import Path

def run_service_command(service, action):
    """Run a service command using the process manager"""
    commands = {
        'websocket-discovery': 'python start_discovery_service.py',
        'celery-worker': 'python -m celery -A app.services.celery_app worker --loglevel=info --pool=solo',
        'celery-beat': 'python -m celery -A app.services.celery_app beat --loglevel=info',
        'fastapi-server': 'python run.py'
    }
    
    if service not in commands:
        print(f"❌ Unknown service: {service}")
        print(f"Available services: {', '.join(commands.keys())}")
        return
    
    if action == 'start':
        print(f"🚀 Starting {service}...")
        subprocess.Popen(commands[service], shell=True)
        print(f"✅ {service} started")
    
    elif action == 'logs':
        log_file = Path(f"logs/{service}.log")
        if log_file.exists():
            print(f"📋 Showing logs for {service}:")
            print("-" * 50)
            with open(log_file, 'r', encoding='utf-8') as f:
                # Show last 50 lines
                lines = f.readlines()
                for line in lines[-50:]:
                    print(line.rstrip())
        else:
            print(f"❌ No log file found for {service}")

def main():
    parser = argparse.ArgumentParser(description='Control Hyperliquid Auto-Trade Services')
    parser.add_argument('action', choices=['start', 'stop', 'restart', 'status', 'logs'], 
                       help='Action to perform')
    parser.add_argument('service', nargs='?', 
                       choices=['websocket-discovery', 'celery-worker', 'celery-beat', 'fastapi-server'],
                       help='Service to control')
    
    args = parser.parse_args()
    
    if args.action in ['start', 'stop', 'restart', 'logs'] and not args.service:
        print(f"❌ Service name required for {args.action} action")
        return
    
    if args.action == 'status':
        print("📊 Service Status:")
        print("For detailed status, use the process manager: python process_manager.py")
        return
    
    run_service_command(args.service, args.action)

if __name__ == "__main__":
    main()
