from celery import current_app as celery_app
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Trader, UserStateHistory, TradeEvent, LeaderboardMetric
from app.core.config import settings
from typing import List, Dict, Any
import logging
from datetime import datetime
import httpx
import asyncio
import redis
import json
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Initialize Redis client for pub/sub
redis_client = redis.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)

def get_db() -> Session:
    """Get database session"""
    return SessionLocal()

@celery_app.task
def task_discover_traders():
    """Task 1: Discover Traders (Service 1)"""
    try:
        asyncio.run(_discover_traders_async())
        logger.info("Completed trader discovery task")
    except Exception as e:
        logger.error(f"Error in task_discover_traders: {e}")

async def _discover_traders_async():
    """Async implementation of trader discovery"""
    db = get_db()
    try:
        # Get popular coins from settings
        popular_coins = settings.POPULAR_COINS
        unique_addresses = set()
        
        async with httpx.AsyncClient() as client:
            # Fetch recent trades for each coin
            for coin in popular_coins:
                try:
                    response = await client.post(
                        "https://api.hyperliquid.xyz/info",
                        json={
                            "type": "recentTrades",
                            "coin": coin
                        }
                    )
                    
                    if response.status_code == 200:
                        trades = response.json()
                        # Extract unique user addresses from trades
                        for trade in trades:
                            if 'user' in trade:
                                unique_addresses.add(trade['user'])
                    
                except Exception as e:
                    logger.error(f"Error fetching trades for {coin}: {e}")
        
        # Process discovered addresses
        new_traders_count = 0
        for address in unique_addresses:
            try:
                # Check if trader already exists
                existing_trader = db.query(Trader).filter(Trader.address == address).first()
                
                if not existing_trader:
                    # Create new trader
                    new_trader = Trader(
                        address=address,
                        first_seen_at=datetime.utcnow(),
                        is_active=True
                    )
                    db.add(new_trader)
                    new_traders_count += 1
            
            except Exception as e:
                logger.error(f"Error processing trader {address}: {e}")
        
        db.commit()
        logger.info(f"Discovered {new_traders_count} new traders from {len(unique_addresses)} total addresses")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in trader discovery: {e}")
    finally:
        db.close()

@celery_app.task
def task_track_traders():
    """Task 2: Track Traders (Service 2)"""
    try:
        asyncio.run(_track_traders_async())
        logger.info("Completed trader tracking task")
    except Exception as e:
        logger.error(f"Error in task_track_traders: {e}")

async def _track_traders_async():
    """Async implementation of trader tracking"""
    db = get_db()
    try:
        # Get all active traders
        active_traders = db.query(Trader).filter(Trader.is_active == True).all()
        
        async with httpx.AsyncClient() as client:
            for trader in active_traders:
                try:
                    # Fetch current user state
                    response = await client.post(
                        "https://api.hyperliquid.xyz/info",
                        json={
                            "type": "clearinghouseState",
                            "user": trader.address
                        }
                    )
                    
                    if response.status_code != 200:
                        logger.warning(f"Failed to fetch state for trader {trader.address}")
                        continue
                    
                    current_state = response.json()
                    
                    # Get most recent state history for comparison
                    previous_state_record = db.query(UserStateHistory).filter(
                        UserStateHistory.trader_id == trader.id
                    ).order_by(UserStateHistory.timestamp.desc()).first()
                    
                    # Implement state change detection
                    if previous_state_record:
                        trade_events = _detect_position_changes(
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
                    
                    # Update trader's last tracked time
                    trader.last_tracked_at = datetime.utcnow()
                    
                except Exception as e:
                    logger.error(f"Error tracking trader {trader.address}: {e}")
        
        db.commit()
        logger.info(f"Tracked {len(active_traders)} traders")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in trader tracking: {e}")
    finally:
        db.close()

@celery_app.task
def task_calculate_leaderboard():
    """Task 3: Calculate Leaderboard (Service 3)"""
    try:
        db = get_db()
        try:
            # Get all traders
            traders = db.query(Trader).all()
            
            for trader in traders:
                try:
                    metrics = {}
                    
                    # Calculate account_age_days
                    if trader.first_seen_at:
                        age_delta = datetime.utcnow() - trader.first_seen_at
                        metrics['account_age_days'] = age_delta.days
                    else:
                        metrics['account_age_days'] = 0
                    
                    # Calculate total_volume_usd
                    total_volume = 0.0
                    open_position_events = db.query(TradeEvent).filter(
                        TradeEvent.trader_id == trader.id,
                        TradeEvent.event_type == 'OPEN_POSITION'
                    ).all()
                    
                    for event in open_position_events:
                        try:
                            details = event.details
                            if details and 'size' in details and 'entry_price' in details:
                                size = float(details['size'])
                                entry_price = float(details['entry_price'])
                                notional_value = abs(size) * entry_price
                                total_volume += notional_value
                        except (ValueError, TypeError, KeyError) as e:
                            logger.warning(f"Error calculating volume for event {event.id}: {e}")
                    
                    metrics['total_volume_usd'] = total_volume
                    
                    # Initialize other metrics with default values
                    metrics.update({
                        'win_rate': 0.0,
                        'avg_risk_ratio': 0.0,
                        'max_drawdown': 0.0,
                        'max_profit_usd': 0.0,
                        'max_loss_usd': 0.0
                    })
                    
                    # Update or create leaderboard metric
                    leaderboard_metric = db.query(LeaderboardMetric).filter(
                        LeaderboardMetric.trader_id == trader.id
                    ).first()
                    
                    if leaderboard_metric:
                        # Update existing metrics
                        for key, value in metrics.items():
                            setattr(leaderboard_metric, key, value)
                        leaderboard_metric.updated_at = datetime.utcnow()
                    else:
                        # Create new metrics entry
                        leaderboard_metric = LeaderboardMetric(
                            trader_id=trader.id,
                            **metrics
                        )
                        db.add(leaderboard_metric)
                
                except Exception as e:
                    logger.error(f"Error calculating metrics for trader {trader.id}: {e}")
            
            db.commit()
            logger.info(f"Updated leaderboard metrics for {len(traders)} traders")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in leaderboard calculation: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in task_calculate_leaderboard: {e}")

def _detect_position_changes(previous_state: Dict, current_state: Dict, timestamp: datetime, trader_id: int) -> List[TradeEvent]:
    """Detect position changes between two state snapshots and return TradeEvent objects"""
    events = []
    
    try:
        # Extract position data from states
        prev_positions = {}
        curr_positions = {}
        
        # Parse previous state positions
        if 'assetPositions' in previous_state:
            for pos in previous_state['assetPositions']:
                if 'position' in pos:
                    coin = pos['position'].get('coin', '')
                    if coin:
                        prev_positions[coin] = pos['position']
        
        # Parse current state positions
        if 'assetPositions' in current_state:
            for pos in current_state['assetPositions']:
                if 'position' in pos:
                    coin = pos['position'].get('coin', '')
                    if coin:
                        curr_positions[coin] = pos['position']
        
        # Compare positions
        all_coins = set(prev_positions.keys()) | set(curr_positions.keys())
        
        for coin in all_coins:
            prev_pos = prev_positions.get(coin)
            curr_pos = curr_positions.get(coin)
            
            prev_size = float(prev_pos['szi']) if prev_pos else 0
            curr_size = float(curr_pos['szi']) if curr_pos else 0
            
            if prev_size == 0 and curr_size != 0:
                # New position opened
                events.append(TradeEvent(
                    trader_id=trader_id,
                    timestamp=timestamp,
                    event_type='OPEN_POSITION',
                    details={
                        'coin': coin,
                        'size': str(curr_size),
                        'side': 'LONG' if curr_size > 0 else 'SHORT',
                        'entry_price': curr_pos.get('entryPx', '0') if curr_pos else '0'
                    }
                ))
            elif prev_size != 0 and curr_size == 0:
                # Position closed
                events.append(TradeEvent(
                    trader_id=trader_id,
                    timestamp=timestamp,
                    event_type='CLOSE_POSITION',
                    details={
                        'coin': coin,
                        'size': str(prev_size),
                        'side': 'LONG' if prev_size > 0 else 'SHORT'
                    }
                ))
    
    except Exception as e:
        logger.error(f"Error detecting position changes: {e}")
    
    return events
