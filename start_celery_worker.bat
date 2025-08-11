@echo off
REM Windows Celery Startup Script
REM This script starts Celery worker and beat scheduler with Windows-compatible settings

echo Starting Celery Worker for Auto-Trade Hyperliquid...

REM Set environment variables
set PYTHONPATH=%CD%
set FORKED_BY_MULTIPROCESSING=1

REM Start Celery worker with solo pool (Windows compatible)
celery -A app.services.celery_app worker --loglevel=info --pool=solo --concurrency=1

pause
