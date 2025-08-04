from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import redis
import json
from datetime import datetime
from app.core.config import settings
from app.database.database import get_db
from app.database.models import Trader, LeaderboardMetric, TradeEvent
from app.services.tasks import track_trader_state

app = FastAPI(
    title="Hyperliquid Auto Trade",
    description="Analysis and copy trading service for Hyperliquid",
    version="1.0.0"
)

# Initialize Redis client
redis_client = redis.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

@app.get("/")
async def root():
    return {"message": "Hyperliquid Auto Trade API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/traders/{address}/track")
async def track_trader(address: str, db: Session = Depends(get_db)):
    """Start tracking a trader by their wallet address."""
    try:
        # Check if trader already exists
        existing_trader = db.query(Trader).filter(Trader.address == address).first()
        if existing_trader:
            return {"message": f"Trader {address} is already being tracked", "trader_id": existing_trader.id}
        
        # Trigger tracking task
        track_trader_state.delay(address)
        
        return {"message": f"Started tracking trader {address}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traders", response_model=List[dict])
async def get_traders(db: Session = Depends(get_db)):
    """Get all tracked traders."""
    traders = db.query(Trader).all()
    return [
        {
            "id": trader.id,
            "address": trader.address,
            "first_seen_at": trader.first_seen_at,
            "last_tracked_at": trader.last_tracked_at,
            "is_active": trader.is_active
        }
        for trader in traders
    ]

@app.get("/api/v1/leaderboard", response_model=List[dict])
async def get_leaderboard(
    sort_by: str = Query("win_rate", description="Field to sort by"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db)
):
    """Get trader leaderboard with Redis caching."""
    try:
        # Create cache key based on sort parameters
        cache_key = f"leaderboard_cache:{sort_by}:{order}"
        
        # Try to get data from Redis cache
        cached_data = redis_client.get(cache_key)
        if cached_data:
            # Cache hit - return cached data
            return json.loads(cached_data)
        
        # Cache miss - query database
        query = db.query(LeaderboardMetric).join(Trader).filter(
            Trader.is_active == True
        )
        
        # Apply sorting
        if hasattr(LeaderboardMetric, sort_by):
            sort_column = getattr(LeaderboardMetric, sort_by)
            if order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            # Default sort by win_rate desc
            query = query.order_by(LeaderboardMetric.win_rate.desc())
        
        leaderboard = query.limit(100).all()
        
        # Serialize data
        leaderboard_data = [
            {
                "trader_id": metric.trader_id,
                "trader_address": metric.trader.address,
                "win_rate": float(metric.win_rate),
                "total_volume_usd": float(metric.total_volume_usd),
                "account_age_days": metric.account_age_days,
                "avg_risk_ratio": float(metric.avg_risk_ratio),
                "max_drawdown": float(metric.max_drawdown),
                "max_profit_usd": float(metric.max_profit_usd),
                "max_loss_usd": float(metric.max_loss_usd),
                "updated_at": metric.updated_at.isoformat() if metric.updated_at else None
            }
            for metric in leaderboard
        ]
        
        # Cache the data for 5 minutes (300 seconds)
        redis_client.setex(
            cache_key,
            300,  # 5 minutes expiration
            json.dumps(leaderboard_data, cls=DateTimeEncoder)
        )
        
        return leaderboard_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching leaderboard: {str(e)}")

@app.get("/leaderboard", response_model=List[dict])
async def get_leaderboard_legacy(db: Session = Depends(get_db)):
    """Legacy leaderboard endpoint for backward compatibility."""
    return await get_leaderboard("win_rate", "desc", db)

@app.get("/traders/{trader_id}/events")
async def get_trader_events(trader_id: int, db: Session = Depends(get_db)):
    """Get trade events for a specific trader."""
    trader = db.query(Trader).filter(Trader.id == trader_id).first()
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    
    events = db.query(TradeEvent).filter(
        TradeEvent.trader_id == trader_id
    ).order_by(TradeEvent.timestamp.desc()).limit(100).all()
    
    return [
        {
            "id": event.id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "details": event.details
        }
        for event in events
    ]

@app.websocket("/ws/v1/trades")
async def websocket_trades(websocket: WebSocket):
    """WebSocket endpoint for real-time trade events."""
    await websocket.accept()
    
    try:
        # Create Redis pub/sub client for real-time updates
        pubsub = redis_client.pubsub()
        pubsub.subscribe("trade_events")
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to real-time trade feed",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Listen for messages from Redis pub/sub
        while True:
            try:
                # Check for new messages (non-blocking)
                message = pubsub.get_message(timeout=1.0)
                
                if message and message['type'] == 'message':
                    try:
                        # Parse and forward trade event
                        trade_data = json.loads(message['data'])
                        await websocket.send_json({
                            "type": "trade_event",
                            "data": trade_data,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except json.JSONDecodeError:
                        # Skip invalid JSON messages
                        continue
                
                # Check if WebSocket is still connected
                try:
                    await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                    
            except Exception as e:
                # Send error message and continue
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing message: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except:
                    # If we can't send error message, connection is likely broken
                    break
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
    finally:
        # Clean up pub/sub connection
        try:
            pubsub.unsubscribe("trade_events")
            pubsub.close()
        except:
            pass

@app.get("/api/v1/cache/clear")
async def clear_cache():
    """Clear all leaderboard cache entries (for testing/admin purposes)."""
    try:
        # Find all leaderboard cache keys
        cache_keys = redis_client.keys("leaderboard_cache:*")
        
        if cache_keys:
            # Delete all cache keys
            redis_client.delete(*cache_keys)
            return {"message": f"Cleared {len(cache_keys)} cache entries"}
        else:
            return {"message": "No cache entries found"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")
