# Start Discovery Service - PowerShell Script
# This script activates the virtual environment and starts the discovery service

Write-Host "🚀 Starting Hyperliquid Trader Discovery Service..." -ForegroundColor Green

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
}

# Start the discovery service
Write-Host "Starting WebSocket Discovery Service..." -ForegroundColor Cyan
python start_discovery_service.py
