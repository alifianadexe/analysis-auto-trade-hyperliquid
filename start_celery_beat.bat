@echo off
REM Windows Celery Beat Scheduler Startup Script
REM This script starts the Celery beat scheduler for periodic tasks

echo Starting Celery Beat Scheduler for Auto-Trade Hyperliquid...

REM Set environment variables
set PYTHONPATH=%CD%

REM Start Celery beat scheduler
celery -A app.services.celery_app beat --loglevel=info

pause
