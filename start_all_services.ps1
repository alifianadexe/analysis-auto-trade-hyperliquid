# Start All Services - PowerShell Script
# This script starts the Hyperliquid Auto-Trade Process Manager

Write-Host "🚀 Starting Hyperliquid Auto-Trade Process Manager..." -ForegroundColor Green

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
}

# Create logs directory if it doesn't exist
if (-not (Test-Path "logs")) {
    Write-Host "Creating logs directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Name "logs"
}

# Start the process manager
Write-Host "Starting process manager..." -ForegroundColor Cyan
python process_manager.py
