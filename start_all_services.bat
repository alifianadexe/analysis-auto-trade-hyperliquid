@echo off
echo 🚀 Starting Hyperliquid Auto-Trade Process Manager...

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Create logs directory if it doesn't exist
if not exist "logs" (
    echo Creating logs directory...
    mkdir logs
)

REM Start the process manager
echo Starting process manager...
python process_manager.py

pause
