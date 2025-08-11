"""
Standalone WebSocket Discovery Service

This service runs independently from Celery to discover new traders
by monitoring Hyperliquid's WebSocket trade feeds.
"""

import asyncio
import json
import logging
import signal
import sys
import websockets
from typing import List, Dict, Any
from datetime import datetime

# Add the project root to Python path for imports
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.config import settings
from app.database.models import Trader
from app.services.tasks.utils import get_db, get_or_create_trader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebSocketDiscoveryService:
    """Standalone WebSocket service for trader discovery"""
    
    def __init__(self):
        self.running = True
        self.websocket_url = "wss://api.hyperliquid.xyz/ws"
        self.coins_to_track = settings.POPULAR_COINS
        self.max_retries = 5
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def stop(self):
        """Stop the discovery service"""
        logger.info("🛑 Stopping WebSocket Discovery Service...")
        self.running = False
        
    async def start(self):
        """Start the WebSocket discovery service"""
        logger.info("🚀 Starting WebSocket Discovery Service")
        logger.info(f"📈 Tracking coins: {self.coins_to_track}")
        
        retry_count = 0
        
        while self.running and retry_count < self.max_retries:
            try:
                logger.info(f"🔌 Connecting to {self.websocket_url}")
                
                async with websockets.connect(self.websocket_url) as websocket:
                    logger.info("✅ Connected to Hyperliquid WebSocket")
                    retry_count = 0  # Reset retry count on successful connection
                    
                    # Subscribe to trade feeds
                    await self._subscribe_to_feeds(websocket)
                    
                    # Listen for messages
                    await self._listen_for_messages(websocket)
                    
            except websockets.exceptions.ConnectionClosed as e:
                if not self.running:
                    break
                    
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)
                logger.warning(f"⚠️ WebSocket connection closed: {e}. Retrying in {wait_time} seconds... (attempt {retry_count}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                if not self.running:
                    break
                    
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)
                logger.error(f"❌ WebSocket error: {e}. Retrying in {wait_time} seconds... (attempt {retry_count}/{self.max_retries})")
                await asyncio.sleep(wait_time)
        
        if retry_count >= self.max_retries:
            logger.error(f"💀 Max retries ({self.max_retries}) exceeded. Discovery service failed.")
        else:
            logger.info("✅ WebSocket Discovery Service stopped gracefully")
    
    async def _subscribe_to_feeds(self, websocket):
        """Subscribe to trade feeds for configured coins"""
        for coin in self.coins_to_track:
            subscription = {
                "method": "subscribe",
                "subscription": {
                    "type": "trades",
                    "coin": coin
                }
            }
            await websocket.send(json.dumps(subscription))
            logger.info(f"✅ Subscribed to trades for {coin}")
    
    async def _listen_for_messages(self, websocket):
        """Listen for and process WebSocket messages"""
        message_count = 0
        
        async for message in websocket:
            if not self.running:
                break
                
            try:
                data = json.loads(message)
                message_count += 1
                
                if message_count % 100 == 0:
                    logger.info(f"📨 Processed {message_count} messages")
                
                # Process trade messages
                if "data" in data and isinstance(data["data"], list):
                    await self._process_trade_messages(data["data"])
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to decode WebSocket message: {e}")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
    
    async def _process_trade_messages(self, trades: List[Dict[str, Any]]):
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


async def main():
    """Main entry point for the discovery service"""
    service = WebSocketDiscoveryService()
    service.setup_signal_handlers()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error in discovery service: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
