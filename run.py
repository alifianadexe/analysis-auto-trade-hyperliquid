#!/usr/bin/env python3
"""
Main entry point for the Hyperliquid Auto Trade application.
"""

import uvicorn
from app.api.main import app

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
