"""
Shared utilities and helper functions for Celery tasks.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.database.models import Trader, TradeEvent

logger = logging.getLogger(__name__)


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


def detect_position_changes(
    previous_state: Dict[str, Any],
    current_state: Dict[str, Any], 
    timestamp: datetime,
    trader_id: int
) -> List[TradeEvent]:
    """Detect position changes between two user states and create trade events"""
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
