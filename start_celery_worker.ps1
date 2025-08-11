# PowerShell Celery Startup Script
# This script starts Celery worker with Windows-compatible settings

Write-Host "Starting Celery Worker for Auto-Trade Hyperliquid..." -ForegroundColor Green

# Set environment variables
$env:PYTHONPATH = Get-Location
$env:FORKED_BY_MULTIPROCESSING = "1"

# Start Celery worker with solo pool (Windows compatible)
try {
    celery -A app.services.celery_app worker --loglevel=info --pool=solo --concurrency=1
}
catch {
    Write-Host "Error starting Celery worker: $_" -ForegroundColor Red
}

Read-Host "Press Enter to exit"
