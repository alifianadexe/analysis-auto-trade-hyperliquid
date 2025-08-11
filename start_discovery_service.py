"""
Start Discovery Service Script

This script starts the standalone WebSocket discovery service.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from app.services.discovery_service import main
    import asyncio
    
    print("🚀 Starting Hyperliquid Trader Discovery Service...")
    asyncio.run(main())
