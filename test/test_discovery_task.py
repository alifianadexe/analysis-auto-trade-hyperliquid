#!/usr/bin/env python3
import asyncio
import logging
from app.services.tasks import task_manage_discovery_stream
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
        recent_traders = db.query(Trader).order_by(Trader.first_seen_at.desc()).limit(5).all()
        
        logger.info(f"Total traders in database: {trader_count}")
        
        if recent_traders:
            logger.info("5 most recently discovered traders:")
            for i, trader in enumerate(recent_traders, 1):
                logger.info(f"{i}. Address: {trader.address}, First seen: {trader.first_seen_at}")
        else:
            logger.info("No traders found in database")
            
    except Exception as e:
        logger.error(f"Error getting trader stats: {e}")
    finally:
        db.close()

def test_discovery_task():
    """Test the trader discovery task"""
    logger.info("=== TRADER DISCOVERY TASK TEST ===")
    
    # Print initial stats
    logger.info("Initial trader statistics:")
    print_trader_stats()
    
    # Run the discovery task
    logger.info("Running trader discovery task...")
    try:
        task_manage_discovery_stream()
        logger.info("Discovery task completed successfully")
    except Exception as e:
        logger.error(f"Error running discovery task: {e}")
    
    # Print final stats to see changes
    logger.info("Final trader statistics after discovery:")
    print_trader_stats()

if __name__ == "__main__":
    test_discovery_task()
