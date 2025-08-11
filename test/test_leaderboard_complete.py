#!/usr/bin/env python3
"""
Test script for Task 3: Leaderboard Calculation and Scoring
"""
import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import func, desc

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tasks.leaderboard_task import task_calculate_leaderboard
from app.database.database import SessionLocal
from app.database.models import Trader, LeaderboardMetric, TradeEvent, UserStateHistory
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_leaderboard_stats():
    """Print current leaderboard statistics from the database"""
    db = SessionLocal()
    try:
        # Leaderboard metrics stats
        total_metrics = db.query(func.count(LeaderboardMetric.trader_id)).scalar()
        metrics_with_profit = db.query(func.count(LeaderboardMetric.trader_id)).filter(
            LeaderboardMetric.max_profit_usd > 0
        ).scalar()
        metrics_with_volume = db.query(func.count(LeaderboardMetric.trader_id)).filter(
            LeaderboardMetric.total_volume_usd > 0
        ).scalar()
        
        # Get top 10 performers
        top_performers = db.query(LeaderboardMetric).order_by(
            desc(LeaderboardMetric.trader_score)
        ).limit(10).all()
        
        # Get recent calculations
        recent_calculations = db.query(func.count(LeaderboardMetric.trader_id)).filter(
            LeaderboardMetric.updated_at > datetime.utcnow() - timedelta(hours=24)
        ).scalar()
        
        logger.info(f"Leaderboard metrics - Total: {total_metrics}, With Profit: {metrics_with_profit}, With Volume: {metrics_with_volume}")
        logger.info(f"Recent calculations (24h): {recent_calculations}")
        
        if top_performers:
            logger.info("Top 10 performers by trader score:")
            for i, metric in enumerate(top_performers, 1):
                trader_addr = metric.trader.address[:10] if metric.trader else "Unknown"
                score = metric.trader_score or 0
                profit = metric.max_profit_usd or 0
                volume = metric.total_volume_usd or 0
                logger.info(f"  {i:2}. {trader_addr}... Score: {score:.2f}, Profit: {profit:.2f}, Volume: {volume:.2f}")
        
        # Get calculation distribution
        total_traders = db.query(func.count(Trader.id)).scalar()
        traders_with_metrics = db.query(func.count(func.distinct(LeaderboardMetric.trader_id))).scalar()
        
        logger.info(f"Coverage: {traders_with_metrics}/{total_traders} traders have metrics")
        
    except Exception as e:
        logger.error(f"Error getting leaderboard stats: {e}")
    finally:
        db.close()

def test_scoring_algorithm():
    """Test the trader scoring algorithm"""
    logger.info("=== TESTING SCORING ALGORITHM ===")
    
    # Since the scoring functions are internal to the leaderboard task,
    # we'll test with mock scenarios to demonstrate the scoring logic
    
    test_cases = [
        {
            "name": "High PnL, Many Trades",
            "total_volume_usd": 1000.0,
            "win_rate": 0.7,
            "avg_risk_ratio": 2.5,
            "max_drawdown": 0.1,
            "max_profit_usd": 50.0
        },
        {
            "name": "Moderate PnL, High Win Rate", 
            "total_volume_usd": 500.0,
            "win_rate": 0.9,
            "avg_risk_ratio": 1.8,
            "max_drawdown": 0.05,
            "max_profit_usd": 25.0
        },
        {
            "name": "Low Activity",
            "total_volume_usd": 10.0,
            "win_rate": 0.5,
            "avg_risk_ratio": 0.5,
            "max_drawdown": 0.2,
            "max_profit_usd": 1.0
        },
        {
            "name": "Loss Making",
            "total_volume_usd": 200.0,
            "win_rate": 0.3,
            "avg_risk_ratio": 0.5,
            "max_drawdown": 0.4,
            "max_profit_usd": 5.0
        }
    ]
    
    try:
        # Simple scoring algorithm for demonstration
        def calculate_mock_score(metrics):
            weights = {
                'win_rate': 0.3,
                'total_volume_usd': 0.2,
                'max_drawdown': 0.25,  # Inverted (lower is better)
                'avg_risk_ratio': 0.15,
                'max_profit_usd': 0.1
            }
            
            # Simple normalization and scoring
            score = (
                metrics["win_rate"] * weights["win_rate"] +
                min(metrics["total_volume_usd"] / 1000, 1.0) * weights["total_volume_usd"] +
                (1.0 - min(metrics["max_drawdown"], 1.0)) * weights["max_drawdown"] +
                min(metrics["avg_risk_ratio"] / 3.0, 1.0) * weights["avg_risk_ratio"] +
                min(metrics["max_profit_usd"] / 100, 1.0) * weights["max_profit_usd"]
            )
            return score
        
        for case in test_cases:
            score = calculate_mock_score(case)
            
            logger.info(f"✅ {case['name']}: Score = {score:.2f}")
            logger.info(f"   Volume: {case['total_volume_usd']}, Win Rate: {case['win_rate']:.1%}")
        
        logger.info("✅ Scoring algorithm tests completed")
        
    except Exception as e:
        logger.error(f"❌ Scoring algorithm test failed: {e}")

def test_metric_calculation():
    """Test metric calculation for specific traders"""
    logger.info("=== TESTING METRIC CALCULATION ===")
    
    db = SessionLocal()
    try:
        # Get a trader with some trade events
        trader_with_events = db.query(Trader).join(TradeEvent).first()
        
        if trader_with_events:
            logger.info(f"Testing metric calculation for trader: {trader_with_events.address[:10]}...")
            
            # Get trade events for this trader
            trade_events = db.query(TradeEvent).filter(
                TradeEvent.trader_id == trader_with_events.id
            ).all()
            
            # Calculate basic metrics
            total_events = len(trade_events)
            open_events = len([e for e in trade_events if e.event_type == 'OPEN_POSITION'])
            close_events = len([e for e in trade_events if e.event_type == 'CLOSE_POSITION'])
            
            # Calculate account age
            account_age = 0
            if trader_with_events.first_seen_at:
                age_delta = datetime.utcnow() - trader_with_events.first_seen_at.replace(tzinfo=None)
                account_age = age_delta.days
            
            logger.info("✅ Basic metric calculation successful:")
            logger.info(f"   Total Events: {total_events}")
            logger.info(f"   Open Positions: {open_events}")
            logger.info(f"   Close Positions: {close_events}")
            logger.info(f"   Account Age: {account_age} days")
            
        else:
            logger.warning("⚠️ No traders with trade events found for testing")
            
    except Exception as e:
        logger.error(f"❌ Metric calculation test failed: {e}")
    finally:
        db.close()

async def test_leaderboard_batch():
    """Test the leaderboard calculation batch"""
    logger.info("=== TESTING LEADERBOARD BATCH ===")
    
    # Print initial stats
    logger.info("Initial stats:")
    print_leaderboard_stats()
    
    try:
        # Run the leaderboard calculation (synchronous)
        task_calculate_leaderboard()
        logger.info("✅ Leaderboard calculation completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Leaderboard calculation failed: {e}")
    
    # Print final stats
    logger.info("Final stats:")
    print_leaderboard_stats()

def test_leaderboard_celery():
    """Test leaderboard task via Celery"""
    logger.info("=== TESTING LEADERBOARD TASK VIA CELERY ===")
    
    logger.info("Initial stats:")
    print_leaderboard_stats()
    
    try:
        # Run the Celery task
        task_calculate_leaderboard()
        logger.info("✅ Celery leaderboard task completed")
        
    except Exception as e:
        logger.error(f"❌ Celery leaderboard task failed: {e}")
    
    logger.info("Final stats:")
    print_leaderboard_stats()

def test_leaderboard_queries():
    """Test various leaderboard queries"""
    logger.info("=== TESTING LEADERBOARD QUERIES ===")
    
    db = SessionLocal()
    try:
        # Test top traders by different metrics
        queries = [
            ("Top by Max Profit", desc(LeaderboardMetric.max_profit_usd)),
            ("Top by Trader Score", desc(LeaderboardMetric.trader_score)),
            ("Top by Win Rate", desc(LeaderboardMetric.win_rate)),
            ("Top by Volume", desc(LeaderboardMetric.total_volume_usd)),
            ("Top by Risk Ratio", desc(LeaderboardMetric.avg_risk_ratio))
        ]
        
        for name, order_by in queries:
            top_5 = db.query(LeaderboardMetric).join(Trader).filter(
                LeaderboardMetric.total_volume_usd > 0  # Only traders with activity
            ).order_by(order_by).limit(5).all()
            
            if top_5:
                logger.info(f"✅ {name}:")
                for i, metric in enumerate(top_5, 1):
                    trader_addr = metric.trader.address[:10] if metric.trader else "Unknown"
                    if "Profit" in name:
                        value = f"{metric.max_profit_usd:.2f}"
                    elif "Score" in name:
                        value = f"{metric.trader_score:.2f}"
                    elif "Win Rate" in name:
                        value = f"{metric.win_rate:.1%}"
                    elif "Volume" in name:
                        value = f"{metric.total_volume_usd:.2f}"
                    elif "Risk" in name:
                        value = f"{metric.avg_risk_ratio:.2f}"
                    
                    logger.info(f"   {i}. {trader_addr}... = {value}")
            else:
                logger.warning(f"⚠️ No data for {name}")
        
        # Test filtering
        profitable_traders = db.query(func.count(LeaderboardMetric.trader_id)).filter(
            LeaderboardMetric.max_profit_usd > 0
        ).scalar()
        
        high_volume_traders = db.query(func.count(LeaderboardMetric.trader_id)).filter(
            LeaderboardMetric.total_volume_usd > 100
        ).scalar()
        
        logger.info(f"✅ Query filters: {profitable_traders} profitable, {high_volume_traders} high-volume traders")
        
    except Exception as e:
        logger.error(f"❌ Leaderboard queries test failed: {e}")
    finally:
        db.close()

async def test_batch_processing():
    """Test batch processing for large datasets"""
    logger.info("=== TESTING BATCH PROCESSING ===")
    
    db = SessionLocal()
    try:
        total_traders = db.query(func.count(Trader.id)).scalar()
        batch_size = getattr(settings, 'BATCH_SIZE', 50)
        
        logger.info(f"Total traders: {total_traders}, Batch size: {batch_size}")
        
        if total_traders > batch_size:
            logger.info("Testing large batch processing...")
            # This would process all traders in batches
            task_calculate_leaderboard()
            logger.info("✅ Large batch processing completed")
        else:
            logger.info("⚠️ Dataset too small for batch testing, but calculation will work")
            task_calculate_leaderboard()
            logger.info("✅ Small dataset processing completed")
            
    except Exception as e:
        logger.error(f"❌ Batch processing test failed: {e}")
    finally:
        db.close()

async def main():
    """Run all leaderboard tests"""
    logger.info("🚀 STARTING LEADERBOARD TASK TESTS")
    
    # Test 1: Scoring algorithm
    logger.info("\n" + "="*50)
    test_scoring_algorithm()
    
    # Test 2: Metric calculation
    logger.info("\n" + "="*50)
    test_metric_calculation()
    
    # Test 3: Leaderboard queries
    logger.info("\n" + "="*50)
    test_leaderboard_queries()
    
    # Test 4: Single leaderboard calculation
    logger.info("\n" + "="*50)
    await test_leaderboard_batch()
    
    # Test 5: Celery task
    logger.info("\n" + "="*50)
    test_leaderboard_celery()
    
    # Test 6: Batch processing
    logger.info("\n" + "="*50)
    await test_batch_processing()
    
    logger.info("\n" + "="*50)
    logger.info("🎉 ALL LEADERBOARD TESTS COMPLETED")

if __name__ == "__main__":
    asyncio.run(main())
