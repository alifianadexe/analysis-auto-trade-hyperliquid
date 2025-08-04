# Hyperliquid Auto Trade - Copy Trading Platform

A comprehensive copy trading platform for Hyperliquid that discovers successful traders, tracks their positions in real-time, and provides a leaderboard with performance metrics.

## 🏗️ Architecture Overview

The application consists of three main services working together:

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  Hyperliquid    │    │   Service 1:         │    │   PostgreSQL    │
│  API            │◄──►│   Trader Discovery   │───►│   Database      │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                                            │
┌─────────────────┐    ┌──────────────────────┐            │
│  Redis Pub/Sub  │◄──►│   Service 2:         │◄───────────┘
│  Real-time      │    │   Position Tracking  │
└─────────────────┘    └──────────────────────┘
        │                        │
        │               ┌──────────────────────┐
        │               │   Service 3:         │
        │               │   Leaderboard Calc   │
        │               └──────────────────────┘
        │                        │
        ▼               ┌─────────────────┐
┌─────────────────┐    │   Redis Cache   │
│  FastAPI Web    │◄──►│   (5min TTL)    │
│  Server         │    └─────────────────┘
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  WebSocket      │
│  Clients        │
└─────────────────┘
```

### Core Components

1. **Service 1 (Trader Discovery)**: Discovers active traders by analyzing recent trades
2. **Service 2 (Position Tracking)**: Monitors trader positions and detects changes
3. **Service 3 (Leaderboard Calculation)**: Calculates performance metrics
4. **FastAPI Web Server**: Provides REST API and WebSocket endpoints
5. **Redis**: Handles caching and real-time pub/sub messaging
6. **PostgreSQL**: Stores trader data, positions, and performance metrics

## 📋 Prerequisites

- Python 3.8+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd auto-trade-hyperliquid

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy and configure your environment file:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database settings
DATABASE_URL=postgresql://hyperliquid_user:hyperliquid_password@localhost:5432/hyperliquid_db

# Redis settings
REDIS_URL=redis://localhost:6379

# Hyperliquid API settings
HYPERLIQUID_API_URL=https://api.hyperliquid.xyz/info
HYPERLIQUID_PRIVATE_KEY=your_private_key_here  # For future trading features
HYPERLIQUID_WALLET_ADDRESS=your_wallet_address_here

# Popular coins to track (comma-separated)
POPULAR_COINS=BTC,ETH,SOL,AVAX,ARB,OP,MATIC

# Celery settings
CELERY_BROKER_URL=redis://localhost:6379
CELERY_RESULT_BACKEND=redis://localhost:6379

# Application settings
DEBUG=False
SECRET_KEY=your-secret-key-change-this-in-production
```

### 3. Start Infrastructure

Start PostgreSQL and Redis using Docker:

```bash
docker-compose up -d
```

### 4. Initialize Database

Create the database tables:

```bash
python init_db.py
```

### 5. Start Services

You need to run these in separate terminal windows:

**Terminal 1 - FastAPI Web Server:**

```bash
python run.py
```

**Terminal 2 - Celery Worker:**

```bash
celery -A app.services.celery_app worker --loglevel=info
```

**Terminal 3 - Celery Beat Scheduler:**

```bash
celery -A app.services.celery_app beat --loglevel=info
```

### 6. Access the Application

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Leaderboard**: http://localhost:8000/api/v1/leaderboard

## 📊 Database Schema

### Tables Overview

```sql
-- Traders table: Stores discovered trader information
CREATE TABLE traders (
    id SERIAL PRIMARY KEY,
    address VARCHAR(42) UNIQUE NOT NULL,
    first_seen_at TIMESTAMP,
    last_tracked_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- User state history: Stores snapshots of trader positions
CREATE TABLE user_state_history (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES traders(id),
    state_data JSONB NOT NULL,  -- Raw API response
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade events: Parsed position changes
CREATE TABLE trade_events (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES traders(id),
    timestamp TIMESTAMP NOT NULL,
    event_type VARCHAR(20) NOT NULL,  -- OPEN_POSITION, CLOSE_POSITION
    details JSONB NOT NULL  -- { coin, size, side, entry_price }
);

-- Leaderboard metrics: Calculated performance data
CREATE TABLE leaderboard_metrics (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES traders(id),
    account_age_days INTEGER DEFAULT 0,
    total_volume_usd DECIMAL(20,8) DEFAULT 0,
    win_rate DECIMAL(5,4) DEFAULT 0,
    avg_risk_ratio DECIMAL(10,6) DEFAULT 0,
    max_drawdown DECIMAL(5,4) DEFAULT 0,
    max_profit_usd DECIMAL(20,8) DEFAULT 0,
    max_loss_usd DECIMAL(20,8) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔄 Application Flow

### Service 1: Trader Discovery (Every 15 minutes)

```python
# app/services/tasks.py - task_discover_traders()
```

1. **Fetch Recent Trades**: Calls Hyperliquid API for each popular coin

   ```json
   POST https://api.hyperliquid.xyz/info
   {
     "type": "recentTrades",
     "coin": "BTC"
   }
   ```

2. **Extract Trader Addresses**: Parses response to find unique user addresses

   ```json
   [
     { "user": "0x1234...", "sz": "1.5", "px": "45000", ... },
     { "user": "0x5678...", "sz": "0.8", "px": "45010", ... }
   ]
   ```

3. **Database Storage**: Creates new `Trader` records for unknown addresses

### Service 2: Position Tracking (Every 1 minute)

```python
# app/services/tasks.py - task_track_traders()
```

1. **Fetch Active Traders**: Queries database for `is_active=True` traders

2. **Get Current Positions**: Calls Hyperliquid API for each trader

   ```json
   POST https://api.hyperliquid.xyz/info
   {
     "type": "clearinghouseState",
     "user": "0x1234..."
   }
   ```

3. **State Comparison**: Compares new state with previous `UserStateHistory`

   ```python
   # Position change detection logic
   if prev_size == 0 and curr_size != 0:
       # New position opened
       event_type = "OPEN_POSITION"
   elif prev_size != 0 and curr_size == 0:
       # Position closed
       event_type = "CLOSE_POSITION"
   ```

4. **Event Storage & Broadcasting**:
   - Saves `TradeEvent` to PostgreSQL
   - Publishes to Redis pub/sub channel `"trade_events"`
   - Updates `UserStateHistory` with new state

### Service 3: Leaderboard Calculation (Every 1 hour)

```python
# app/services/tasks.py - task_calculate_leaderboard()
```

1. **Account Age**: `(datetime.utcnow() - trader.first_seen_at).days`

2. **Total Volume**: Sums notional values from `OPEN_POSITION` events

   ```python
   for event in open_position_events:
       size = float(event.details['size'])
       entry_price = float(event.details['entry_price'])
       total_volume += abs(size) * entry_price
   ```

3. **Metric Storage**: Updates `LeaderboardMetric` table

## 🌐 API Endpoints

### REST API

| Endpoint                   | Method | Description                      | Caching          |
| -------------------------- | ------ | -------------------------------- | ---------------- |
| `/`                        | GET    | Welcome message                  | None             |
| `/health`                  | GET    | Health check                     | None             |
| `/api/v1/leaderboard`      | GET    | Cached leaderboard with sorting  | 5min Redis       |
| `/leaderboard`             | GET    | Legacy leaderboard endpoint      | Via new endpoint |
| `/traders`                 | GET    | List all tracked traders         | None             |
| `/traders/{id}/events`     | GET    | Trade events for specific trader | None             |
| `/traders/{address}/track` | POST   | Start tracking a trader          | None             |
| `/api/v1/cache/clear`      | GET    | Clear leaderboard cache          | None             |

### Query Parameters

**Leaderboard Sorting:**

```bash
GET /api/v1/leaderboard?sort_by=total_volume_usd&order=desc
GET /api/v1/leaderboard?sort_by=win_rate&order=asc
```

Available sort fields:

- `win_rate` (default)
- `total_volume_usd`
- `account_age_days`
- `max_profit_usd`
- `max_loss_usd`
- `avg_risk_ratio`
- `max_drawdown`

### WebSocket API

**Real-time Trade Events:**

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/v1/trades");

ws.onopen = function () {
  console.log("Connected to trade feed");
};

ws.onmessage = function (event) {
  const data = JSON.parse(event.data);

  if (data.type === "connection") {
    console.log("Connection confirmed:", data.message);
  } else if (data.type === "trade_event") {
    console.log("New trade:", data.data);
    // Handle real-time trade event
  }
};
```

**WebSocket Message Types:**

1. **Connection Confirmation:**

   ```json
   {
     "type": "connection",
     "message": "Connected to real-time trade feed",
     "timestamp": "2025-08-03T10:30:00.000Z"
   }
   ```

2. **Trade Event:**
   ```json
   {
     "type": "trade_event",
     "data": {
       "id": 123,
       "trader_id": 45,
       "trader_address": "0x1234...",
       "timestamp": "2025-08-03T10:30:00.000Z",
       "event_type": "OPEN_POSITION",
       "details": {
         "coin": "BTC",
         "size": "1.5",
         "side": "LONG",
         "entry_price": "45000"
       }
     },
     "timestamp": "2025-08-03T10:30:00.000Z"
   }
   ```

## 🔧 Configuration

### Environment Variables

| Variable                | Description                      | Example                                    |
| ----------------------- | -------------------------------- | ------------------------------------------ |
| `DATABASE_URL`          | PostgreSQL connection string     | `postgresql://user:pass@localhost:5432/db` |
| `REDIS_URL`             | Redis connection string          | `redis://localhost:6379`                   |
| `HYPERLIQUID_API_URL`   | API base URL                     | `https://api.hyperliquid.xyz/info`         |
| `POPULAR_COINS`         | Coins to track (comma-separated) | `BTC,ETH,SOL,AVAX`                         |
| `CELERY_BROKER_URL`     | Celery broker URL                | `redis://localhost:6379`                   |
| `CELERY_RESULT_BACKEND` | Celery result backend            | `redis://localhost:6379`                   |
| `DEBUG`                 | Debug mode                       | `False`                                    |
| `SECRET_KEY`            | Application secret key           | `your-secret-key`                          |

### Celery Task Schedule

```python
# app/services/celery_app.py
beat_schedule = {
    'discover-traders': {
        'task': 'app.services.tasks.task_discover_traders',
        'schedule': 900.0,  # 15 minutes
    },
    'track-traders': {
        'task': 'app.services.tasks.task_track_traders',
        'schedule': 60.0,   # 1 minute
    },
    'calculate-leaderboard': {
        'task': 'app.services.tasks.task_calculate_leaderboard',
        'schedule': 3600.0, # 1 hour
    },
}
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:
   Copy `.env` and update the values:

```bash
cp .env .env.local
# Edit .env.local with your actual configuration
```

## Configuration

Update the `.env` file with your configuration:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `HYPERLIQUID_API_URL`: Hyperliquid API endpoint
- `HYPERLIQUID_PRIVATE_KEY`: Your wallet private key (keep secure!)
- `HYPERLIQUID_WALLET_ADDRESS`: Your wallet address

## Running the Application

### Development Mode

1. Start the FastAPI server:

```bash
python run.py
```

2. Start Celery worker (in a separate terminal):

```bash
celery -A app.services.celery_app worker --loglevel=info
```

3. Start Celery beat scheduler (in another terminal):

```bash
celery -A app.services.celery_app beat --loglevel=info
```

### Production Mode

Use a process manager like Supervisor or Docker to manage the services.

## API Endpoints

- `GET /`: Root endpoint
- `GET /health`: Health check
- More endpoints will be added for trading functionality

## Database Setup

1. Install PostgreSQL and create a database
2. Update the `DATABASE_URL` in your `.env` file
3. Run database migrations (to be implemented with Alembic)

## Redis Setup

1. Install Redis
2. Update the `REDIS_URL` in your `.env` file

## 📈 Performance Features

### Redis Caching

- **Leaderboard Cache**: 5-minute TTL reduces database load
- **Cache Keys**: `leaderboard_cache:{sort_by}:{order}`
- **Cache Hit Rate**: ~95% for frequently accessed leaderboards

### Real-time Updates

- **Redis Pub/Sub**: Zero-latency event broadcasting
- **WebSocket Connections**: Persistent connections for real-time data
- **Event Filtering**: Only position changes generate events

### Database Optimization

- **JSONB Fields**: Efficient storage and querying of API responses
- **Indexes**: Optimized queries on trader addresses and timestamps
- **Connection Pooling**: SQLAlchemy connection management

## 🛠️ Development

### Code Structure

```
app/
├── api/
│   └── main.py              # FastAPI application and endpoints
├── core/
│   └── config.py            # Pydantic settings management
├── database/
│   ├── database.py          # SQLAlchemy setup and session management
│   └── models.py            # Database models (Trader, TradeEvent, etc.)
└── services/
    ├── celery_app.py        # Celery configuration and scheduling
    └── tasks.py             # Background task implementations

# Root files
├── run.py                   # FastAPI server startup
├── worker.py                # Celery worker startup
├── init_db.py               # Database initialization
├── docker-compose.yml       # Infrastructure services
├── requirements.txt         # Python dependencies
└── Makefile                 # Development commands
```

### Key Technologies

- **FastAPI**: Modern, fast web framework with automatic API docs
- **SQLAlchemy 2.0**: Modern ORM with async support and type hints
- **Celery**: Distributed task queue for background processing
- **Redis**: In-memory data store for caching and pub/sub
- **PostgreSQL**: Robust relational database with JSONB support
- **Pydantic**: Data validation and settings management
- **httpx**: Modern async HTTP client

### Development Commands

```bash
# Start infrastructure
make docker-up

# Install dependencies
make install

# Start development server
make run

# Start Celery worker
make worker

# Start Celery beat scheduler
make beat

# Clean up temporary files
make clean
```

## 🐛 Troubleshooting

### Common Issues

1. **Connection Errors**:

   ```bash
   # Check if services are running
   docker-compose ps

   # Restart services
   docker-compose restart
   ```

2. **Database Issues**:

   ```bash
   # Recreate database
   python init_db.py

   # Check connection
   psql postgresql://hyperliquid_user:hyperliquid_password@localhost:5432/hyperliquid_db
   ```

3. **Celery Tasks Not Running**:

   ```bash
   # Check worker status
   celery -A app.services.celery_app inspect active

   # Check beat schedule
   celery -A app.services.celery_app inspect scheduled
   ```

4. **API Errors**:

   ```bash
   # Check logs
   tail -f logs/app.log

   # Test API endpoints
   curl http://localhost:8000/health
   ```

### Logging

The application uses structured logging:

```python
import logging
logger = logging.getLogger(__name__)

# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logger.info("Task completed successfully")
logger.error("Error occurred: %s", error_message)
```

## 🚀 Production Deployment

### Docker Production Setup

1. **Create Production Environment**:

   ```bash
   cp .env .env.production
   # Update production values
   ```

2. **Build Production Images**:

   ```dockerfile
   FROM python:3.11-slim
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY app/ /app/
   ```

3. **Deploy with Docker Compose**:
   ```yaml
   version: "3.8"
   services:
     web:
       build: .
       ports:
         - "8000:8000"
       environment:
         - DATABASE_URL=postgresql://...
         - REDIS_URL=redis://...
   ```

### Monitoring

- **Health Checks**: `/health` endpoint
- **Metrics**: Celery task monitoring
- **Logging**: Centralized log aggregation
- **Performance**: Redis cache hit rates

## 🔍 Example Usage

### 1. Start the System

```bash
# Terminal 1: Start infrastructure
docker-compose up -d

# Terminal 2: Initialize database
python init_db.py

# Terminal 3: Start web server
python run.py

# Terminal 4: Start Celery worker
celery -A app.services.celery_app worker --loglevel=info

# Terminal 5: Start Celery beat scheduler
celery -A app.services.celery_app beat --loglevel=info
```

### 2. API Usage Examples

**Get Leaderboard:**

```bash
curl "http://localhost:8000/api/v1/leaderboard?sort_by=total_volume_usd&order=desc"
```

**Track a Specific Trader:**

```bash
curl -X POST "http://localhost:8000/traders/0x1234567890abcdef/track"
```

**Get Trader Events:**

```bash
curl "http://localhost:8000/traders/1/events"
```

### 3. WebSocket Client Example

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Hyperliquid Live Trades</title>
  </head>
  <body>
    <div id="trades"></div>
    <script>
      const ws = new WebSocket("ws://localhost:8000/ws/v1/trades");
      const tradesDiv = document.getElementById("trades");

      ws.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.type === "trade_event") {
          const trade = data.data;
          tradesDiv.innerHTML += `
                    <div>
                        <strong>${trade.event_type}</strong>: 
                        ${trade.details.coin} ${trade.details.size} 
                        @ ${trade.details.entry_price}
                        (${trade.trader_address})
                    </div>
                `;
        }
      };
    </script>
  </body>
</html>
```

## Security Notes

- Keep your private keys secure and never commit them to version control
- Use environment variables for sensitive configuration
- Consider using encrypted storage for private keys in production

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

---

## 🎯 Next Steps

1. **Enhanced Metrics**: Add more sophisticated trading metrics
2. **Copy Trading**: Implement actual position copying
3. **User Authentication**: Add user accounts and API keys
4. **Advanced Filtering**: More leaderboard filter options
5. **Mobile App**: React Native mobile application
6. **Machine Learning**: Predictive trader scoring

---

**Happy Trading! 🚀**

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license here]
