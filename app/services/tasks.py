from celery import current_app as celery_app
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Trader, UserStateHistory, TradeEvent, LeaderboardMetric
from app.core.config import settings
from app.services.hyperliquid_client import hyperliquid_client
from typing import List, Dict, Any
import logging
from datetime import datetime
import asyncio
import redis
import json
import websockets
import time
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Initialize Redis client for pub/sub
redis_client = redis.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)

def _detect_position_changes(
    previous_state: Dict[str, Any],
    current_state: Dict[str, Any],
    timestamp: datetime,
    trader_id: int
) -> List[TradeEvent]:
    """Detect position changes between two user states and create trade events"""
    trade_events = []
    
    try:
        # Extract asset positions from states
        prev_positions = {}
        current_positions = {}
        
        # Parse previous positions
        if 'assetPositions' in previous_state:
            for pos in previous_state['assetPositions']:
                coin = pos.get('position', {}).get('coin')
                if coin:
                    prev_positions[coin] = pos
        
        # Parse current positions
        if 'assetPositions' in current_state:
            for pos in current_state['assetPositions']:
                coin = pos.get('position', {}).get('coin')
                if coin:
                    current_positions[coin] = pos
        
        # Find all coins that had position changes
        all_coins = set(prev_positions.keys()) | set(current_positions.keys())
        
        for coin in all_coins:
            prev_pos = prev_positions.get(coin, {})
            curr_pos = current_positions.get(coin, {})
            
            prev_size = float(prev_pos.get('position', {}).get('szi', 0))
            curr_size = float(curr_pos.get('position', {}).get('szi', 0))
            
            # Detect size changes
            if abs(prev_size - curr_size) > 1e-8:  # Use small epsilon for float comparison
                size_change = curr_size - prev_size
                
                # Determine event type
                if prev_size == 0 and curr_size != 0:
                    event_type = "position_opened"
                elif prev_size != 0 and curr_size == 0:
                    event_type = "position_closed"
                elif (prev_size > 0 and curr_size > 0) or (prev_size < 0 and curr_size < 0):
                    event_type = "position_increased" if abs(curr_size) > abs(prev_size) else "position_decreased"
                else:
                    event_type = "position_flipped"  # Changed from long to short or vice versa
                
                # Create trade event
                trade_event = TradeEvent(
                    trader_id=trader_id,
                    timestamp=timestamp,
                    event_type=event_type,
                    details={
                        "coin": coin,
                        "previous_size": prev_size,
                        "current_size": curr_size,
                        "size_change": size_change,
                        "previous_position": prev_pos,
                        "current_position": curr_pos
                    }
                )
                trade_events.append(trade_event)
        
        return trade_events
        
    except Exception as e:
        logger.error(f"Error detecting position changes: {e}")
        return []

def get_db() -> Session:
    """Get database session"""
    return SessionLocal()

def get_or_create_trader(db: Session, address: str) -> Trader:
    """Helper function to get existing trader or create new one"""
    try:
        # Check if trader already exists
        existing_trader = db.query(Trader).filter(Trader.address == address).first()
        
        if existing_trader:
            return existing_trader
        
        # Create new trader
        new_trader = Trader(
            address=address,
            first_seen_at=datetime.utcnow(),
            is_active=True
        )
        db.add(new_trader)
        db.commit()
        db.refresh(new_trader)
        
        logger.info(f"Created new trader: {address}")
        return new_trader
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating trader {address}: {e}")
        raise

@celery_app.task
def task_manage_discovery_stream():
    """REVISED Task 1: Discover Traders via WebSocket (Service 1)"""
    try:
        asyncio.run(_manage_discovery_stream_async())
        logger.info("Discovery stream task completed")
    except Exception as e:
        logger.error(f"Error in task_manage_discovery_stream: {e}")

async def _manage_discovery_stream_async():
    """Async implementation of WebSocket-based trader discovery"""
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            async with websockets.connect(settings.WEBSOCKET_URL) as websocket:
                logger.info("Connected to Hyperliquid WebSocket")
                
                # Subscribe to trades for each popular coin
                for coin in settings.POPULAR_COINS:
                    subscription_msg = {
                        "method": "subscribe",
                        "subscription": {
                            "type": "trades",
                            "coin": coin
                        }
                    }
                    await websocket.send(json.dumps(subscription_msg))
                    logger.info(f"Subscribed to trades for {coin}")
                
                # Reset retry count on successful connection
                retry_count = 0
                
                # Listen for incoming messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Process trade messages
                        if data.get("channel") == "trades" and "data" in data:
                            trades = data["data"]
                            if isinstance(trades, list):
                                await _process_trade_messages(trades)
                            else:
                                await _process_trade_messages([trades])
                                
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse WebSocket message: {message}")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            retry_count += 1
            wait_time = min(60, 2 ** retry_count)  # Exponential backoff, max 60 seconds
            logger.warning(f"WebSocket connection closed. Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            retry_count += 1
            wait_time = min(60, 2 ** retry_count)
            logger.error(f"WebSocket error: {e}. Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)
    
    logger.error(f"Max retries ({max_retries}) exceeded. Discovery stream task failed.")

async def _process_trade_messages(trades: List[Dict[str, Any]]):
    """Process incoming trade messages and discover new traders"""
    db = get_db()
    try:
        new_traders_found = 0
        
        for trade in trades:
            try:
                # Extract trader addresses from the "users" array in the trade data
                if "users" in trade and isinstance(trade["users"], list):
                    for user_address in trade["users"]:
                        if not user_address:
                            continue
                            
                        # Use helper function to get or create trader
                        trader = get_or_create_trader(db, user_address)
                        # This will be true for new traders
                        if hasattr(trader, 'first_seen_at') and trader.first_seen_at:
                            if not hasattr(trader, '_sa_instance_state'):  # Check for new traders
                                new_traders_found += 1
                        
            except Exception as e:
                logger.error(f"Error processing trade message: {e}")
        
        if new_traders_found > 0:
            logger.info(f"Discovered {new_traders_found} new traders from WebSocket feed")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing trade messages: {e}")
    finally:
        db.close()

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
                        # Use timezone-aware datetime to match trader.first_seen_at
                        now = datetime.now(trader.first_seen_at.tzinfo)
                        age_delta = now - trader.first_seen_at
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
