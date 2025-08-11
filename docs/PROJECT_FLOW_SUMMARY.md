# Project Flow Documentation - Updated Architecture

## Overview

This document describes the current architecture and flow of the Hyperliquid Auto-Trade copy trading platform after the Linux migration and architectural improvements.

## System Architecture

### 4-Service Architecture

1. **WebSocket Discovery Service** (Standalone)
2. **Celery Worker** (2 tasks)
3. **Celery Beat Scheduler** (Task scheduler)
4. **FastAPI Web Server** (API + UI)

### Process Management

- **Linux Process Manager**: `process_manager.py` orchestrates all services
- **Native Linux features**: Process groups, signal handling, auto-restart
- **Service dependencies**: Proper startup order and dependency management

## Service Details

### 1. WebSocket Discovery Service

**File**: `app/services/discovery_service.py`
**Launcher**: `start_discovery_service.py`

**Purpose**: Real-time trader discovery through WebSocket streams

**Flow**:

1. Connects to `wss://api.hyperliquid.xyz/ws`
2. Subscribes to trade feeds for popular coins (BTC, ETH, SOL, etc.)
3. Processes incoming trade messages to extract trader addresses
4. Creates new `Trader` records for unknown addresses
5. Handles reconnection with exponential backoff

**Benefits**:

- ✅ Zero API weight cost
- ✅ Real-time discovery
- ✅ Unlimited scalability
- ✅ No rate limiting concerns

### 2. Celery Worker (2 Tasks)

**Configuration**: `app/services/celery_app.py`
**Tasks**:

- `app/services/tasks/tracking_task.py`
- `app/services/tasks/leaderboard_task.py`

#### Task A: Trader Position Tracking

**Task**: `task_track_traders_batch()`
**Schedule**: Every 75 seconds
**File**: `app/services/tasks/tracking_task.py`

**Flow**:

1. **Queue Selection**: Gets 50 traders (BATCH_SIZE) ordered by `last_tracked_at ASC NULLS FIRST`
2. **API Calls**: Fetches current state for each trader (weight: 2 per trader = 100 total)
3. **Change Detection**: Compares with previous state to detect position changes
4. **Event Generation**: Creates `TradeEvent` records for position changes
5. **Redis Publishing**: Publishes events to `trade_events` channel for real-time updates
6. **Queue Rotation**: Updates `last_tracked_at` to send trader to back of queue
7. **State Storage**: Saves new `UserStateHistory` record

**Rate Limiting**: 50 traders × 2 weight = 100 weight per 75 seconds = 80 weight/minute (safe under 1200 limit)

#### Task B: Leaderboard Calculation

**Task**: `task_calculate_leaderboard()`
**Schedule**: Every 10 minutes  
**File**: `app/services/tasks/leaderboard_task.py`

**Flow**:

1. **Individual Metrics**: Calculates metrics for each active trader
   - Account age days
   - Total volume USD
   - Win rate (estimated)
   - Average risk ratio
   - Max drawdown
   - Max profit/loss USD
2. **Normalization**: Normalizes all metrics to 0-1 scale
3. **Weighted Scoring**: Applies weights to calculate composite `trader_score`
4. **Database Update**: Updates `LeaderboardMetric` table

**Scoring Weights**:

- Win rate: 30%
- Total volume: 20%
- Max drawdown: 25% (inverted - lower is better)
- Risk ratio: 15%
- Max profit: 10%

### 3. Celery Beat Scheduler

**Purpose**: Manages periodic task execution
**Tasks Scheduled**:

- `track-traders-batch`: Every 75 seconds
- `calculate-leaderboard`: Every 10 minutes

### 4. FastAPI Web Server

**File**: `app/api/main.py`
**Launcher**: `run.py`

**Features**:

- REST API endpoints (rate-safe, no direct API calls)
- WebSocket real-time updates (`/ws/v1/updates`)
- Cached leaderboard with Redis (5-minute TTL)
- System statistics and health checks

## Data Flow

### Real-time Data Path

```
WebSocket → Discovery Service → Database (Traders)
                ↓
Database (TradeEvents) ← Tracking Task ← API Calls
                ↓
Redis Pub/Sub → WebSocket Clients ← FastAPI Server
```

### Batch Processing Path

```
Database Queue → Tracking Task → Position Detection → Event Storage
                                      ↓
LeaderboardMetric ← Leaderboard Task ← TradeEvent Analysis
                                      ↓
FastAPI Cache ← Redis Cache ← Database Query
```

## Performance Characteristics

### Rate Limiting Compliance

- **WebSocket Discovery**: 0 API weight (unlimited)
- **Position Tracking**: 80 weight/minute (93% under limit)
- **Total Safety Margin**: 1120 weight/minute buffer

### Scalability

- **Trader Discovery**: Unlimited (WebSocket-based)
- **Position Tracking**: Scales with BATCH_SIZE configuration
- **Queue Management**: Fair rotation ensures all traders tracked
- **Database**: Optimized indexes for queue operations

### Reliability

- **Auto-restart**: Services restart automatically on crash (up to 5 attempts)
- **Process Groups**: Clean shutdown of all child processes
- **Signal Handling**: Proper SIGTERM/SIGKILL handling
- **Error Recovery**: Graceful handling of API failures and WebSocket disconnects

## Configuration

### Key Settings

```env
BATCH_SIZE=50                    # Traders per tracking batch
POPULAR_COINS=BTC,ETH,SOL,AVAX   # Coins to track via WebSocket
WEBSOCKET_URL=wss://api.hyperliquid.xyz/ws
HYPERLIQUID_API_URL=https://api.hyperliquid.xyz/info
```

### Service Commands

```bash
# Start all services
python process_manager.py

# Individual services
python start_discovery_service.py
python -m celery -A app.services.celery_app worker --concurrency=4
python -m celery -A app.services.celery_app beat
python run.py
```

## Monitoring

### Service Health

- Real-time status display every 30 seconds
- Individual log files in `logs/` directory
- Process PID, uptime, and restart count tracking

### Key Metrics

- New trader discovery rate
- Position tracking success rate
- API weight usage vs. limits
- Queue rotation efficiency
- WebSocket connection stability

### Log Files

```
logs/
├── process_manager.log
├── websocket-discovery.log
├── celery-worker.log
├── celery-beat.log
└── fastapi-server.log
```

## Deployment

### Linux Requirements

- Python 3.8+
- PostgreSQL 15+
- Redis 7+
- Linux OS (uses os.setsid, SIGTERM/SIGKILL)

### Production Startup

```bash
chmod +x start_all_services.sh
./start_all_services.sh
```

This architecture provides a robust, scalable, and rate-limit-compliant solution for copy trading on Hyperliquid with proper Linux process management and service orchestration.
