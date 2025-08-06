import logging
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import func

from app.database.database import get_db, SessionLocal
from app.database.models import Trader, UserStateHistory
from app.services.tasks import _track_traders_batch_async
from app.services.hyperliquid_client import HyperliquidClient
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

async def test_track_traders_batch():
    """Test the trader tracking functionality"""
    logger.info("=== TESTING TRADER TRACKING BATCH ===")
    
    # Get database connection
    db = SessionLocal()
    
    try:
        # Get total trader count
        total_traders = db.query(func.count(Trader.id)).scalar()
        logger.info(f"Total traders in database: {total_traders}")
        
        # Check if we have any traders that need tracking
        untracked_traders = db.query(func.count(Trader.id)).filter(
            Trader.last_tracked_at.is_(None)
        ).scalar()
        
        tracked_traders = db.query(func.count(Trader.id)).filter(
            Trader.last_tracked_at.is_not(None)
        ).scalar()
        
        logger.info(f"Untracked traders: {untracked_traders}")
        logger.info(f"Previously tracked traders: {tracked_traders}")
        
        # Get 5 sample traders for tracking
        sample_traders = db.query(Trader).order_by(
            Trader.last_tracked_at.asc().nulls_first()
        ).limit(5).all()
        
        logger.info(f"Selected {len(sample_traders)} sample traders for tracking test:")
        for i, trader in enumerate(sample_traders, 1):
            logger.info(f"{i}. Address: {trader.address}, Last tracked: {trader.last_tracked_at}")
        
        # Check for existing state histories
        state_history_count = db.query(func.count(UserStateHistory.id)).scalar()
        logger.info(f"Current state history records: {state_history_count}")
        
        # Run the tracking task
        logger.info("Running trader tracking task...")
        await _track_traders_batch_async()
        
        # Check updated tracking status
        db.refresh(sample_traders[0])  # Refresh the first trader to get updated data
        logger.info(f"First trader updated last_tracked_at: {sample_traders[0].last_tracked_at}")
        
        # Check new state histories
        new_state_history_count = db.query(func.count(UserStateHistory.id)).scalar()
        logger.info(f"New state history record count: {new_state_history_count}")
        logger.info(f"Added {new_state_history_count - state_history_count} new state history records")
        
        # Get the latest state history for first sample trader
        latest_state = db.query(UserStateHistory).filter(
            UserStateHistory.trader_id == sample_traders[0].id
        ).order_by(UserStateHistory.timestamp.desc()).first()
        
        if latest_state:
            logger.info(f"Latest state record for {sample_traders[0].address}:")
            logger.info(f"Timestamp: {latest_state.timestamp}")
            logger.info(f"Sample state data: {json.dumps(latest_state.state_data)[:200]}...")  # First 200 chars
        else:
            logger.info(f"No state history found for {sample_traders[0].address}")
        
    except Exception as e:
        logger.error(f"Error testing trader tracking: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_track_traders_batch())
