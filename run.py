#!/usr/bin/env python3
"""
Main entry point for the Hyperliquid Auto Trade application.

ARCHITECTURE OVERVIEW:
======================

This application now consists of 3 separate services:

1. **FastAPI Web Server** (this file):
   - REST API for data access
   - Run: python run.py

2. **Celery Workers** (async batch processing):
   - Trader position tracking
   - Leaderboard calculation
   - Run: python -m celery -A app.services.celery_app worker --concurrency=4

3. **WebSocket Discovery Service** (standalone):
   - Real-time trader discovery via WebSocket
   - Run: python start_discovery_service.py

4. **Celery Beat Scheduler** (task scheduling):
   - Schedules periodic Celery tasks
   - Run: python -m celery -A app.services.celery_app beat

STARTUP ORDER:
==============
1. Start WebSocket Discovery Service first
2. Start Celery Worker
3. Start Celery Beat Scheduler
4. Start FastAPI Web Server (this script)
"""

import uvicorn
from app.api.main import app

if __name__ == "__main__":
    print("🚀 Starting Hyperliquid Auto Trade FastAPI Server...")
    print("📋 Make sure other services are running:")
    print("   1. WebSocket Discovery: python start_discovery_service.py")
    print("   2. Celery Worker: python -m celery -A app.services.celery_app worker --concurrency=4")
    print("   3. Celery Beat: python -m celery -A app.services.celery_app beat")
    print("")
    
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
