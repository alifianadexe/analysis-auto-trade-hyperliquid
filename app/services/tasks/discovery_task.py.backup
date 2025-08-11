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
from app.database.models import Trader
from .utils import get_db, get_or_create_trader

logger = logging.getLogger(__name__)


@celery_app.task
def task_manage_discovery_stream():
    """REVISED Task 1: Discover Traders via WebSocket (Service 1)"""
    logger.info("🚀 Starting discovery task")
    
    try:
        import asyncio
        asyncio.run(_manage_discovery_stream_async())
        logger.info("✅ Discovery stream task completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in task_manage_discovery_stream: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


async def _manage_discovery_stream_async():
    """Async implementation of WebSocket-based trader discovery"""
    logger.info("🔌 Starting WebSocket connection process")
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Connect to Hyperliquid WebSocket
            websocket_url = "wss://api.hyperliquid.xyz/ws"
            logger.info(f"Attempting to connect to {websocket_url}")
            
            async with websockets.connect(websocket_url) as websocket:
                logger.info("✅ Connected to Hyperliquid WebSocket")
                
                # Subscribe to trade feeds for popular coins from configuration
                coins_to_track = settings.POPULAR_COINS
                logger.info(f"📈 Tracking coins from config: {coins_to_track}")
                
                for coin in coins_to_track:
                    subscription = {
                        "method": "subscribe",
                        "subscription": {
                            "type": "trades",
                            "coin": coin
                        }
                    }
                    await websocket.send(json.dumps(subscription))
                    logger.info(f"✅ Subscribed to trades for {coin}")
                
                # Listen for messages
                message_count = 0
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        message_count += 1
                        
                        if message_count % 100 == 0:  # Log every 100 messages
                            logger.info(f"📨 Processed {message_count} messages")
                        
                        # Process trade messages
                        if "data" in data and isinstance(data["data"], list):
                            await _process_trade_messages(data["data"])
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to decode WebSocket message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            retry_count += 1
            wait_time = min(60, 2 ** retry_count)  # Exponential backoff, max 60 seconds
            logger.warning(f"⚠️ WebSocket connection closed: {e}. Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            retry_count += 1
            wait_time = min(60, 2 ** retry_count)
            logger.error(f"❌ WebSocket error: {e}. Retrying in {wait_time} seconds... (attempt {retry_count}/{max_retries})")
            await asyncio.sleep(wait_time)
    
    logger.error(f"💀 Max retries ({max_retries}) exceeded. Discovery stream task failed.")


async def _process_trade_messages(trades: List[Dict[str, Any]]):
    """Process incoming trade messages and discover new traders"""
    db = get_db()
    try:
        new_traders_found = 0
        processed_addresses = set()  # Avoid counting duplicates in same batch
        
        for trade in trades:
            try:
                # Extract trader addresses from the "users" array in the trade data
                if "users" in trade and isinstance(trade["users"], list):
                    for user_address in trade["users"]:
                        if not user_address or user_address in processed_addresses:
                            continue
                        
                        processed_addresses.add(user_address)
                        
                        # Check if trader already exists
                        existing_trader = db.query(Trader).filter(Trader.address == user_address).first()
                        
                        if not existing_trader:
                            # Create new trader
                            trader = get_or_create_trader(db, user_address)
                            if trader:
                                new_traders_found += 1
                                logger.debug(f"Discovered new trader: {user_address[:10]}...")
                        
            except Exception as e:
                logger.error(f"Error processing trade message: {e}")
        
        if new_traders_found > 0:
            logger.info(f"Discovered {new_traders_found} new traders from WebSocket feed")
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing trade messages: {e}")
    finally:
        db.close()
