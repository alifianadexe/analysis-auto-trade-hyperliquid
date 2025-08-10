"""
Task 1: WebSocket Trader Discovery

This task connects to Hyperliquid's WebSocket feed to discover new traders
by monitoring trade messages and extracting trader addresses.
"""

import asyncio
import json
import logging
import websockets
from typing import List, Dict, Any
from datetime import datetime

from app.services.celery_app import celery_app
from app.core.config import settings
from .utils import get_db, get_or_create_trader

logger = logging.getLogger(__name__)


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
            # Connect to Hyperliquid WebSocket
            websocket_url = "wss://api.hyperliquid.xyz/ws"
            async with websockets.connect(websocket_url) as websocket:
                logger.info("Connected to Hyperliquid WebSocket")
                
                # Subscribe to trade feeds for popular coins
                coins_to_track = ["BTC", "ETH", "SOL", "AVAX", "ARB", "OP", "MATIC"]
                
                for coin in coins_to_track:
                    subscription = {
                        "method": "subscribe",
                        "subscription": {
                            "type": "trades",
                            "coin": coin
                        }
                    }
                    await websocket.send(json.dumps(subscription))
                    logger.info(f"Subscribed to trades for {coin}")
                
                # Listen for messages
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Process trade messages
                        if "data" in data and isinstance(data["data"], list):
                            await _process_trade_messages(data["data"])
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to decode WebSocket message: {e}")
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
