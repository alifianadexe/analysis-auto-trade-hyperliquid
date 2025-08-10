"""
Task 2: Trader Position Tracking

This task tracks traders in batches by fetching their current state from the
Hyperliquid API and detecting position changes to generate trade events.
"""

import asyncio
import json
import logging
import redis
from typing import Dict, Any
from datetime import datetime

from app.services.celery_app import celery_app
from app.database.models import Trader, UserStateHistory, TradeEvent
from app.services.hyperliquid_client import hyperliquid_client
from app.core.config import settings
from .utils import get_db, detect_position_changes

logger = logging.getLogger(__name__)

# Initialize Redis client for pub/sub
redis_client = redis.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)


@celery_app.task
def task_track_traders_batch():
    """REVISED Task 2: Track Traders in Batches (Service 2)"""
    try:
        asyncio.run(_track_traders_batch_async())
        logger.info("Completed trader batch tracking task")
    except Exception as e:
        logger.error(f"Error in task_track_traders_batch: {e}")


async def _track_traders_batch_async():
    """Async implementation of batched trader tracking"""
    db = get_db()
    try:
        # Query for BATCH_SIZE active traders, ordered by last_tracked_at ASC (oldest first)
        batch_traders = db.query(Trader).filter(
            Trader.is_active == True
        ).order_by(
            Trader.last_tracked_at.asc().nulls_first()
        ).limit(settings.BATCH_SIZE).all()
        
        if not batch_traders:
            logger.info("No active traders to track")
            return
        
        logger.info(f"Tracking batch of {len(batch_traders)} traders")
        successful_tracks = 0
        
        for trader in batch_traders:
            try:
                # Get current user state using the optimized client (weight: 2)
                current_state = await hyperliquid_client.get_user_state(trader.address)
                
                if current_state is None:
                    logger.warning(f"Failed to fetch state for trader {trader.address}")
                    continue
                
                # Get most recent state history for comparison
                previous_state_record = db.query(UserStateHistory).filter(
                    UserStateHistory.trader_id == trader.id
                ).order_by(UserStateHistory.timestamp.desc()).first()
                
                # Implement state change detection
                if previous_state_record:
                    trade_events = detect_position_changes(
                        previous_state_record.state_data,
                        current_state,
                        datetime.utcnow(),
                        trader.id
                    )
                    
                    # Save trade events and publish to Redis
                    for event in trade_events:
                        db.add(event)
                        db.flush()  # Ensure event gets an ID
                        
                        # Publish to Redis pub/sub for real-time updates
                        try:
                            event_data = {
                                "id": event.id,
                                "trader_id": event.trader_id,
                                "trader_address": trader.address,
                                "timestamp": event.timestamp.isoformat(),
                                "event_type": event.event_type,
                                "details": event.details
                            }
                            redis_client.publish("trade_events", json.dumps(event_data))
                        except Exception as e:
                            logger.error(f"Error publishing trade event to Redis: {e}")
                
                # Save new state history
                new_state_history = UserStateHistory(
                    trader_id=trader.id,
                    state_data=current_state,
                    timestamp=datetime.utcnow()
                )
                db.add(new_state_history)
                
                # CRITICAL: Update last_tracked_at to send trader to back of queue
                trader.last_tracked_at = datetime.utcnow()
                
                successful_tracks += 1
                
            except Exception as e:
                logger.error(f"Error tracking trader {trader.address}: {e}")
        
        db.commit()
        logger.info(f"Successfully tracked {successful_tracks}/{len(batch_traders)} traders")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch trader tracking: {e}")
    finally:
        db.close()
