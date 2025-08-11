# Task Architecture Summary - Current Implementation

## Overview

The Hyperliquid copy trading platform now uses a **4-service architecture** with a **standalone WebSocket discovery service** and **2 Celery tasks**. This design provides optimal rate limiting compliance, real-time performance, and Linux-native process management.

## Current Architecture

### Service 1: WebSocket Discovery Service (Standalone)

**Implementation**: `app/services/discovery_service.py`
**Launcher**: `start_discovery_service.py`
**Management**: Controlled by `process_manager.py`

**Key Features**:

- **Standalone Process**: No longer a Celery task
- **Persistent Connection**: Maintains WebSocket connection to `wss://api.hyperliquid.xyz/ws`
- **Multi-coin Subscriptions**: Tracks BTC, ETH, SOL, AVAX, ARB, OP, MATIC
- **Real-time Discovery**: Extracts trader addresses from trade streams
- **Auto-reconnection**: Exponential backoff reconnection logic
- **Zero API Weight**: No rate limiting concerns

### Service 2: Celery Worker (2 Tasks)

**Configuration**: `app/services/celery_app.py`

#### Task A: Batched Position Tracking

**Task**: `task_track_traders_batch()`
**File**: `app/services/tasks/tracking_task.py`
**Schedule**: Every 75 seconds

**Implementation**:

- **Queue-based Processing**: Uses `last_tracked_at ASC NULLS FIRST` ordering
- **Batch Size**: Configurable (default: 50 traders per batch)
- **API Calls**: 2 weight per trader × 50 = 100 weight per batch
- **Rate Compliance**: 80 weight/minute (93% under 1200 limit)
- **Position Detection**: Compares states to detect OPEN/CLOSE/INCREASE/DECREASE
- **Real-time Publishing**: Sends events to Redis pub/sub for WebSocket clients
- **Queue Rotation**: Updates `last_tracked_at` for fair rotation

#### Task B: Leaderboard Calculation

**Task**: `task_calculate_leaderboard()`
**File**: `app/services/tasks/leaderboard_task.py`
**Schedule**: Every 10 minutes

**Implementation**:

- **Individual Metrics**: Account age, volume, win rate, risk ratio, drawdown
- **Normalization**: Min-max scaling to [0,1] range
- **Weighted Scoring**: Composite `trader_score` with configurable weights
- **Database Updates**: Saves to `LeaderboardMetric` table

### Service 3: Celery Beat Scheduler

**Purpose**: Manages periodic task execution
**Configuration**:

```python
beat_schedule = {
    "track-traders-batch": {
        "task": "app.services.tasks.tracking_task.task_track_traders_batch",
        "schedule": 75.0,
    },
    "calculate-leaderboard": {
        "task": "app.services.tasks.leaderboard_task.task_calculate_leaderboard",
        "schedule": 600.0,  # 10 minutes
    },
}
```

### Service 4: FastAPI Web Server

**File**: `app/api/main.py`
**Features**:

- **Rate-safe Endpoints**: No direct API calls, serves cached data
- **WebSocket Distribution**: Real-time updates via `/ws/v1/updates`
- **Redis Caching**: 5-minute TTL for leaderboard data
- **System Statistics**: Health monitoring endpoints

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
