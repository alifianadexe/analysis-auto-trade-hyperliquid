#!/usr/bin/env python3
import asyncio
import logging
import sys

# Configure logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import our application code
try:
    from app.database.database import SessionLocal
    from app.database.models import Trader
    from app.core.config import settings
    import websockets
    import json
    
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
    
    # Helper function to get or create trader
    def get_or_create_trader(db, address):
        from datetime import datetime
        
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
    
    # Process trade messages
    async def process_trade_messages(trades):
        db = SessionLocal()
        try:
            new_traders_found = 0
            
            for trade in trades:
                try:
                    # Extract trader address from trade data
                    if "addr" in trade:
                        trader_address = trade["addr"]
                        
                        # Skip if address is None or empty
                        if not trader_address:
                            continue
                        
                        # Get or create trader
                        trader = get_or_create_trader(db, trader_address)
                        new_traders_found += 1
                        
                except Exception as e:
                    logger.error(f"Error processing trade: {e}")
            
            if new_traders_found > 0:
                logger.info(f"Discovered {new_traders_found} new traders")
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing trade messages: {e}")
        finally:
            db.close()
    
    # Main WebSocket test function
    async def test_websocket_discovery(duration=30):
        """Test WebSocket discovery for a specified duration in seconds"""
        logger.info(f"Starting WebSocket discovery test (will run for {duration} seconds)...")
        
        try:
            async with websockets.connect(settings.WEBSOCKET_URL) as websocket:
                logger.info(f"Connected to {settings.WEBSOCKET_URL}")
                
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
                
                # Set end time
                end_time = asyncio.get_event_loop().time() + duration
                
                # Listen for messages until duration expires
                while asyncio.get_event_loop().time() < end_time:
                    try:
                        # Set a timeout so we can check if we've exceeded duration
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        
                        # Process the message
                        data = json.loads(message)
                        logger.info(f"Received message: {message[:500]}...")
                        
                        # Process trade messages
                        if data.get("channel") == "trades" and "data" in data:
                            trades = data["data"]
                            logger.info(f"Found trade data: {trades}")
                            if isinstance(trades, list):
                                await process_trade_messages(trades)
                            else:
                                await process_trade_messages([trades])
                                
                    except asyncio.TimeoutError:
                        # Just a timeout for our loop check, not an error
                        pass
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse WebSocket message")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    if __name__ == "__main__":
        # Get test duration from command line argument, default to 30 seconds
        duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
        
        logger.info("=== WEBSOCKET DISCOVERY TEST ===")
        
        # Print initial stats
        logger.info("Initial trader statistics:")
        print_trader_stats()
        
        # Run the WebSocket discovery test
        asyncio.run(test_websocket_discovery(duration))
        
        # Print final stats
        logger.info("Final trader statistics after discovery:")
        print_trader_stats()
        
        logger.info("Test completed")
        
except Exception as e:
    logging.error(f"Setup error: {e}", exc_info=True)
    sys.exit(1)
