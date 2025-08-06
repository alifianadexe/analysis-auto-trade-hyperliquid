# Configuration Migration - BATCH_SIZE and WEBSOCKET_URL

## Changes Made

Successfully moved hardcoded configuration constants to the environment variables and config system.

### Files Modified:

#### 1. `.env` 
**Added:**
```properties
# Task configuration
BATCH_SIZE=50
WEBSOCKET_URL=wss://api.hyperliquid.xyz/ws
```

#### 2. `app/core/config.py`
**Added:**
```python
# Task configuration settings
BATCH_SIZE: int = Field(default=50, description="Number of traders to process per batch")
WEBSOCKET_URL: str = Field(default="wss://api.hyperliquid.xyz/ws", description="Hyperliquid WebSocket URL")
```

**Fixed:** 
- Renamed `POPULAR_COINS` field to `POPULAR_COINS_STR` to avoid property naming conflict
- Updated property method to use `POPULAR_COINS_STR`

#### 3. `app/services/tasks.py`
**Removed:**
```python
# Configuration constants
BATCH_SIZE = 10  # Safe batch size for rate limiting (50 * 20 weight = 1000, under 1200 limit)
WEBSOCKET_URL = "wss://api.hyperliquid.xyz/ws"
```

**Updated references:**
- `WEBSOCKET_URL` → `settings.WEBSOCKET_URL`
- `BATCH_SIZE` → `settings.BATCH_SIZE`

#### 4. `app/services/celery_app.py`
**Updated comment** to reference configurable batch size instead of hardcoded value.

## Benefits:

1. **Environment-based Configuration:** Both values can now be customized via environment variables
2. **Centralized Config:** All configuration is managed through the Pydantic settings system
3. **Type Safety:** Configuration values are properly typed and validated
4. **Default Values:** Sensible defaults are provided if environment variables aren't set
5. **Documentation:** Field descriptions explain the purpose of each configuration

## Usage:

Users can now customize these values by:
1. Setting environment variables: `BATCH_SIZE=30` and `WEBSOCKET_URL=wss://custom.endpoint.com/ws`
2. Or by updating the `.env` file directly

The application will automatically pick up these values through the Pydantic settings system.
