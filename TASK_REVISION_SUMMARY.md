# Task Revision Summary - WebSocket + Batching Strategy

## Overview

Revised the copy trading tasks due to rate limiting concerns with the original HTTP polling approach. The new implementation uses WebSocket for real-time trader discovery and batched REST API calls for position tracking.

## Key Changes Made

### 1. Service 1 - Trader Discovery (REVISED)

**Before:** `task_discover_traders()` - HTTP polling every 15 minutes
**After:** `task_manage_discovery_stream()` - WebSocket connection management

**New Implementation:**

- Maintains persistent WebSocket connection to `wss://api.hyperliquid.xyz/ws`
- Subscribes to trades for popular coins (`BTC`, `ETH`, `SOL`, etc.)
- Automatically discovers traders in real-time from trade streams
- Includes reconnection logic with exponential backoff
- Scheduled every 30 minutes to restart connection for reliability

### 2. Service 2 - Position Tracking (REVISED)

**Before:** `task_track_traders()` - All traders every minute
**After:** `task_track_traders_batch()` - Batched processing with rate limiting

**New Implementation:**

- Processes exactly 50 traders per batch (BATCH_SIZE=50)
- Uses `last_tracked_at` field with proper indexing for queue management
- Respects rate limits: 50 traders × 20 weight = 1000 weight (safe under 1200 limit)
- Scheduled every 75 seconds for safe rate limiting
- Automatic queue rotation ensures all traders get tracked

### 3. Service 3 - Leaderboard Calculation (UNCHANGED)

- `task_calculate_leaderboard()` remains the same
- Still runs every hour to calculate metrics

## Rate Limiting Strategy

### WebSocket Advantages

- Real-time trader discovery with zero API weight cost
- No rate limiting concerns for trader discovery
- Immediate detection of new traders

### Batch Processing Benefits

- Controlled rate limiting: 1000 weight per 75 seconds = 800 weight/minute (under 1200 limit)
- Queue-based processing ensures fair rotation
- Database optimized with `last_tracked_at` index for efficient querying

## Database Optimizations

- Added critical index on `Trader.last_tracked_at` for efficient batch querying
- Queue management automatically sends tracked traders to back of queue
- Optimized for batching scenarios with proper ordering

## Implementation Details

### New Dependencies

- Added `websockets==12.0` to requirements.txt
- WebSocket connection management with proper error handling

### New Functions

- `task_manage_discovery_stream()` - WebSocket connection management
- `_manage_discovery_stream_async()` - Async WebSocket implementation
- `_process_trade_messages()` - Process incoming trade data
- `task_track_traders_batch()` - Batched position tracking
- `_track_traders_batch_async()` - Async batch processing implementation
- `_detect_position_changes()` - Helper function for position change detection

### Celery Beat Schedule Updates

```python
"manage-discovery-stream": {
    "task": "app.services.tasks.task_manage_discovery_stream",
    "schedule": 30.0 * 60,  # Every 30 minutes
},
"track-traders-batch": {
    "task": "app.services.tasks.task_track_traders_batch",
    "schedule": 75.0,  # Every 75 seconds
},
```

## Benefits of Revision

1. **Rate Limit Compliance:** Guaranteed to stay under 1200 weight/minute limit
2. **Real-time Discovery:** WebSocket provides immediate trader detection
3. **Scalability:** Batch processing scales efficiently with trader count
4. **Reliability:** Proper error handling and reconnection logic
5. **Performance:** Database optimizations for batch querying

## Monitoring Considerations

### WebSocket Connection

- Monitor connection stability and reconnection frequency
- Log new trader discovery rates from WebSocket feeds

### Batch Processing

- Monitor batch processing times and success rates
- Track queue rotation efficiency (time between trader updates)

### Rate Limiting

- Monitor actual API weight usage vs. theoretical limits
- Alert if approaching rate limit thresholds

The revised implementation provides a robust, scalable, and rate-limit-compliant solution for the Hyperliquid copy trading platform.
