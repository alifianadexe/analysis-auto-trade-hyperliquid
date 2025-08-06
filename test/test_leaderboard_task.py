import logging
from sqlalchemy import func
from datetime import datetime

from app.database.database import SessionLocal
from app.database.models import Trader, LeaderboardMetric, TradeEvent
from app.services.tasks import task_calculate_leaderboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def test_leaderboard_calculation():
    """Test the leaderboard calculation task"""
    logger.info("=== TESTING LEADERBOARD CALCULATION ===")
    
    # Get database connection
    db = SessionLocal()
    
    try:
        # Check current leaderboard metrics
        current_metrics_count = db.query(func.count(LeaderboardMetric.trader_id)).scalar()
        logger.info(f"Current leaderboard metrics count: {current_metrics_count}")
        
        # Check if we have any trade events
        trade_events_count = db.query(func.count(TradeEvent.id)).scalar()
        logger.info(f"Current trade events count: {trade_events_count}")
        
        # Get total trader count
        total_traders = db.query(func.count(Trader.id)).scalar()
        logger.info(f"Total traders in database: {total_traders}")
        
        # Run the leaderboard calculation task
        logger.info("Running leaderboard calculation task...")
        task_calculate_leaderboard()
        
        # Check new metrics count
        new_metrics_count = db.query(func.count(LeaderboardMetric.trader_id)).scalar()
        logger.info(f"New leaderboard metrics count: {new_metrics_count}")
        logger.info(f"Added {new_metrics_count - current_metrics_count} new leaderboard metrics")
        
        # Show sample of top traders by volume
        top_traders = db.query(Trader, LeaderboardMetric).join(
            LeaderboardMetric, Trader.id == LeaderboardMetric.trader_id
        ).order_by(
            LeaderboardMetric.total_volume_usd.desc()
        ).limit(10).all()
        
        logger.info("Top 10 traders by volume:")
        for i, (trader, metrics) in enumerate(top_traders, 1):
            logger.info(f"{i}. Address: {trader.address}, Volume: ${metrics.total_volume_usd:.2f}, Age: {metrics.account_age_days} days")
        
    except Exception as e:
        logger.error(f"Error testing leaderboard calculation: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_leaderboard_calculation()
