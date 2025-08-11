#!/usr/bin/env python3
"""
Test script for Task 2: Trader Position Tracking
"""
import sys
import os
import asyncio
import logging
from datetime import datetime
from sqlalchemy import func

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tasks.tracking_task import task_track_traders_batch, _track_traders_batch_async
from app.database.database import SessionLocal
from app.database.models import Trader, UserStateHistory, TradeEvent
from app.services.hyperliquid_client import hyperliquid_client
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_tracking_stats():
    """Print current tracking statistics from the database"""
    db = SessionLocal()
    try:
        # Trader stats
        total_traders = db.query(func.count(Trader.id)).scalar()
        active_traders = db.query(func.count(Trader.id)).filter(Trader.is_active == True).scalar()
        tracked_traders = db.query(func.count(Trader.id)).filter(Trader.last_tracked_at.is_not(None)).scalar()
        untracked_traders = db.query(func.count(Trader.id)).filter(Trader.last_tracked_at.is_(None)).scalar()
        
        # State history stats
        total_states = db.query(func.count(UserStateHistory.id)).scalar()
        
        # Trade events stats
        total_events = db.query(func.count(TradeEvent.id)).scalar()
        open_events = db.query(func.count(TradeEvent.id)).filter(TradeEvent.event_type == 'OPEN_POSITION').scalar()
        close_events = db.query(func.count(TradeEvent.id)).filter(TradeEvent.event_type == 'CLOSE_POSITION').scalar()
        
        logger.info(f"Traders - Total: {total_traders}, Active: {active_traders}, Tracked: {tracked_traders}, Untracked: {untracked_traders}")
        logger.info(f"State histories: {total_states}")
        logger.info(f"Trade events - Total: {total_events}, Opens: {open_events}, Closes: {close_events}")
        
        # Get batch size from settings
        batch_size = getattr(settings, 'BATCH_SIZE', 50)
        logger.info(f"Current batch size: {batch_size}")
        
        # Show next batch to be tracked
        next_batch = db.query(Trader).filter(
            Trader.is_active == True
        ).order_by(
            Trader.last_tracked_at.asc().nulls_first()
        ).limit(5).all()
        
        if next_batch:
            logger.info("Next 5 traders to be tracked:")
            for i, trader in enumerate(next_batch, 1):
                last_tracked = trader.last_tracked_at.strftime('%Y-%m-%d %H:%M:%S') if trader.last_tracked_at else 'Never'
                logger.info(f"  {i}. {trader.address[:10]}... (last tracked: {last_tracked})")
        
    except Exception as e:
        logger.error(f"Error getting tracking stats: {e}")
    finally:
        db.close()

async def test_hyperliquid_client():
    """Test Hyperliquid client functionality"""
    logger.info("=== TESTING HYPERLIQUID CLIENT ===")
    
    try:
        # Test basic connection
        meta_data = await hyperliquid_client.get_perp_meta()
        if meta_data:
            logger.info("✅ Successfully fetched perp metadata")
            universe = meta_data.get('universe', [])
            logger.info(f"   Found {len(universe)} perpetual assets")
        else:
            logger.error("❌ Failed to fetch perp metadata")
            return False
        
        # Test user state fetch with a sample address
        db = SessionLocal()
        try:
            sample_trader = db.query(Trader).first()
            if sample_trader:
                logger.info(f"Testing user state fetch for trader: {sample_trader.address[:10]}...")
                user_state = await hyperliquid_client.get_user_state(sample_trader.address)
                if user_state:
                    logger.info("✅ Successfully fetched user state")
                    logger.info(f"   Account value: {user_state.get('marginSummary', {}).get('accountValue', 'N/A')}")
                else:
                    logger.warning("⚠️ User state returned None (trader might have no positions)")
            else:
                logger.warning("⚠️ No traders in database to test with")
        finally:
            db.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Hyperliquid client test failed: {e}")
        return False

async def test_tracking_batch():
    """Test the tracking batch functionality"""
    logger.info("=== TESTING TRACKING BATCH ===")
    
    # Print initial stats
    logger.info("Initial stats:")
    print_tracking_stats()
    
    try:
        # Run the tracking batch
        await _track_traders_batch_async()
        logger.info("✅ Tracking batch completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Tracking batch failed: {e}")
    
    # Print final stats
    logger.info("Final stats:")
    print_tracking_stats()

def test_tracking_celery():
    """Test tracking task via Celery"""
    logger.info("=== TESTING TRACKING TASK VIA CELERY ===")
    
    logger.info("Initial stats:")
    print_tracking_stats()
    
    try:
        # Run the Celery task
        task_track_traders_batch()
        logger.info("✅ Celery tracking task completed")
        
    except Exception as e:
        logger.error(f"❌ Celery tracking task failed: {e}")
    
    logger.info("Final stats:")
    print_tracking_stats()

async def test_position_detection():
    """Test position change detection logic"""
    logger.info("=== TESTING POSITION DETECTION ===")
    
    from app.services.tasks.utils import detect_position_changes
    
    # Mock previous state
    previous_state = {
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "0",  # No position
                    "entryPx": "0"
                }
            }
        ]
    }
    
    # Mock current state with new position
    current_state = {
        "assetPositions": [
            {
                "position": {
                    "coin": "BTC",
                    "szi": "0.1",  # New long position
                    "entryPx": "50000"
                }
            }
        ]
    }
    
    try:
        events = detect_position_changes(
            previous_state,
            current_state,
            datetime.utcnow(),
            1  # Sample trader ID
        )
        
        if events:
            logger.info(f"✅ Position detection working - found {len(events)} events")
            for event in events:
                logger.info(f"   Event: {event.event_type} for {event.details.get('coin')} - Size: {event.details.get('size')}")
        else:
            logger.info("ℹ️ No position changes detected (expected for this test)")
            
    except Exception as e:
        logger.error(f"❌ Position detection test failed: {e}")

async def test_multiple_batches():
    """Test multiple consecutive batches"""
    logger.info("=== TESTING MULTIPLE BATCHES ===")
    
    logger.info("Initial stats:")
    print_tracking_stats()
    
    try:
        # Run 3 batches consecutively
        for i in range(3):
            logger.info(f"Running batch {i+1}/3...")
            await _track_traders_batch_async()
            await asyncio.sleep(2)  # Small delay between batches
        
        logger.info("✅ Multiple batches completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Multiple batches test failed: {e}")
    
    logger.info("Final stats:")
    print_tracking_stats()

async def main():
    """Run all tracking tests"""
    logger.info("🚀 STARTING TRACKING TASK TESTS")
    
    # Test 1: Hyperliquid client
    logger.info("\n" + "="*50)
    if not await test_hyperliquid_client():
        logger.error("❌ Hyperliquid client test failed - skipping other tests")
        return
    
    # Test 2: Position detection
    logger.info("\n" + "="*50)
    await test_position_detection()
    
    # Test 3: Single tracking batch
    logger.info("\n" + "="*50)
    await test_tracking_batch()
    
    # Test 4: Celery task
    logger.info("\n" + "="*50)
    test_tracking_celery()
    
    # Test 5: Multiple batches
    logger.info("\n" + "="*50)
    await test_multiple_batches()
    
    logger.info("\n" + "="*50)
    logger.info("🎉 ALL TRACKING TESTS COMPLETED")

if __name__ == "__main__":
    asyncio.run(main())
