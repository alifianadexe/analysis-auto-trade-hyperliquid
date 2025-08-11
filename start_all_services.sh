#!/bin/bash

# Hyperliquid Auto-Trade Services Startup Script for Linux
# This script starts all services using the process manager

echo "🚀 Starting Hyperliquid Auto-Trade Services..."
echo "============================================="

# Check if Python virtual environment exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if required environment file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if logs directory exists
if [ ! -d "logs" ]; then
    echo "📁 Creating logs directory..."
    mkdir -p logs
fi

echo "🔧 Starting Process Manager..."
python process_manager.py
