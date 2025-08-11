#!/usr/bin/env python3
"""
Test script for Task 1: WebSocket Trader Discovery
"""
import sys
import os
import asyncio
import logging
import time
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tasks.discovery_task import task_manage_discovery_stream, _manage_discovery_stream_async
from app.database.database import SessionLocal
from app.database.models import Trader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_trader_stats():
    """Print current trader statistics from the database"""
    db = SessionLocal()
    try:
        trader_count = db.query(Trader).count()
        active_count = db.query(Trader).filter(Trader.is_active == True).count()
        recent_traders = db.query(Trader).order_by(Trader.first_seen_at.desc()).limit(5).all()
        
        logger.info(f"Total traders: {trader_count}, Active: {active_count}")
        
        if recent_traders:
            logger.info("5 most recent traders:")
            for i, trader in enumerate(recent_traders, 1):
                logger.info(f"  {i}. {trader.address[:10]}... (first seen: {trader.first_seen_at})")
        else:
            logger.info("No traders found")
            
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
    finally:
        db.close()

async def test_websocket_connection():
    """Test basic WebSocket connection"""
    logger.info("Testing WebSocket connection...")
    try:
        import websockets
        import json
        
        async with websockets.connect("wss://api.hyperliquid.xyz/ws") as ws:
            # Test subscription
            subscription = {
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": "SUI"
                }
            }
            await ws.send(json.dumps(subscription))
            logger.info("✅ WebSocket connection successful")
            
            # Get a few messages to test
            for i in range(3):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(message)
                    logger.info(f"✅ Received message {i+1}: {type(data)}")
                    if "data" in data:
                        logger.info(f"   Trade data length: {len(data['data'])}")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Timeout waiting for WebSocket message")
                    break
                    
    except Exception as e:
        logger.error(f"❌ WebSocket connection failed: {e}")
        return False
    
    return True

async def test_discovery_short():
    """Test discovery task for a short duration"""
    logger.info("=== TESTING DISCOVERY TASK (30 seconds) ===")
    
    # Print initial stats
    logger.info("Initial stats:")
    print_trader_stats()
    
    # Run discovery for 30 seconds
    discovery_task = asyncio.create_task(_manage_discovery_stream_async())
    
    try:
        await asyncio.sleep(10)  # Run for 30 seconds
        discovery_task.cancel()
        try:
            await discovery_task
        except asyncio.CancelledError:
            logger.info("Discovery task cancelled after 30 seconds")
    except Exception as e:
        logger.error(f"Error during discovery test: {e}")
    
    # Print final stats
    logger.info("Final stats:")
    print_trader_stats()

def test_discovery_celery():
    """Test discovery task via Celery (run for 60 seconds then interrupt)"""
    logger.info("=== TESTING DISCOVERY TASK VIA CELERY (60 seconds) ===")
    
    logger.info("Initial stats:")
    print_trader_stats()
    
    try:
        # Start the task in background
        import threading
        import time
        
        task_result = None
        task_error = None
        
        def run_task():
            nonlocal task_result, task_error
            try:
                task_manage_discovery_stream()
                task_result = "completed"
            except Exception as e:
                task_error = e
        
        # Start task in background thread
        task_thread = threading.Thread(target=run_task)
        task_thread.daemon = True
        task_thread.start()
        
        # Wait 60 seconds
        start_time = time.time()
        while time.time() - start_time < 60:
            time.sleep(5)
            if not task_thread.is_alive():
                break
            logger.info(f"Task running for {int(time.time() - start_time)} seconds...")
        
        logger.info("✅ Discovery task ran successfully for 60 seconds")
        
    except Exception as e:
        logger.error(f"❌ Celery task failed: {e}")
    
    logger.info("Final stats:")
    print_trader_stats()

async def main():
    """Run all discovery tests"""
    logger.info("🚀 STARTING DISCOVERY TASK TESTS")
    
    # Test 1: WebSocket connection
    logger.info("\n" + "="*50)
    if not await test_websocket_connection():
        logger.error("❌ WebSocket test failed - skipping other tests")
        return
    
    # Test 2: Short discovery test
    logger.info("\n" + "="*50)
    await test_discovery_short()
    
    # Test 3: Celery task test
    logger.info("\n" + "="*50)
    test_discovery_celery()
    
    logger.info("\n" + "="*50)
    logger.info("🎉 ALL DISCOVERY TESTS COMPLETED")

if __name__ == "__main__":
    asyncio.run(main())
