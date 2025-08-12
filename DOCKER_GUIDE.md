# 🐳 Docker Quick Start Guide

This guide will get your Hyperliquid copy trading platform running in Docker in under 5 minutes.

## Prerequisites

- Docker Desktop installed and running
- Git (to clone the repository)

## Step-by-Step Deployment

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd auto-trade-hyperliquid
```

### 2. Start All Services

```bash
# Start infrastructure and application services
docker-compose up -d
```

This command will:

- ✅ Start PostgreSQL database
- ✅ Start Redis cache
- ✅ Build your application image
- ✅ Start discovery service (WebSocket trader discovery)
- ✅ Start Celery worker (position tracking)
- ✅ Start Celery beat scheduler
- ✅ Start FastAPI web server

### 3. Initialize Database

Wait for services to start (about 30 seconds), then run:

**Linux/Mac:**

```bash
chmod +x docker-init.sh
./docker-init.sh
```

**Windows:**

```powershell
.\docker-init.ps1
```

### 4. Access Your Platform

- 🌐 **API Documentation**: http://localhost:8000/docs
- 💓 **Health Check**: http://localhost:8000/health
- 🏆 **Leaderboard**: http://localhost:8000/api/v1/leaderboard
- 📊 **WebSocket Updates**: ws://localhost:8000/ws/v1/updates

## Service Management

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f discovery-service
docker-compose logs -f celery-worker
docker-compose logs -f fastapi-server
```

### Restart Services

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart discovery-service
```

### Stop Services

```bash
# Stop all services (keep data)
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## Configuration (Optional)

The default configuration works out of the box. To customize:

1. Copy the environment template:

```bash
cp .env.docker .env
```

2. Edit `.env` with your preferred settings:

```env
# Popular coins to track (comma-separated)
POPULAR_COINS=BTC,ETH,SOL,AVAX,ARB,OP,MATIC

# Batch size for tracking (25-100)
BATCH_SIZE=50

# Your Hyperliquid wallet (for future features)
HYPERLIQUID_PRIVATE_KEY=your_private_key_here
HYPERLIQUID_WALLET_ADDRESS=your_wallet_address_here
```

3. Restart services:

```bash
docker-compose down && docker-compose up -d
```

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker-compose ps

# Check specific service logs
docker-compose logs discovery-service
```

### Database Connection Issues

```bash
# Restart infrastructure services
docker-compose restart postgres redis

# Wait 30 seconds, then restart application services
docker-compose restart discovery-service celery-worker celery-beat fastapi-server
```

### Reset Everything

```bash
# Complete reset (removes all data)
docker-compose down -v
docker-compose up -d
./docker-init.sh  # or .\docker-init.ps1 on Windows
```

## Production Deployment

For production use:

1. **Update security settings** in `.env`:

```env
SECRET_KEY=your-very-secure-secret-key-here
POSTGRES_PASSWORD=your-secure-database-password
```

2. **Configure reverse proxy** (nginx/traefik) for SSL termination

3. **Set up monitoring** using the health check endpoint: `/health`

4. **Configure log rotation** for the `./logs/` directory

## Architecture

The Docker deployment includes:

- **PostgreSQL 15**: Database for trader data and metrics
- **Redis 7**: Message broker and caching layer
- **Discovery Service**: Real-time WebSocket trader discovery
- **Celery Worker**: Batched position tracking (4 workers)
- **Celery Beat**: Task scheduler (75s tracking, 10min leaderboard)
- **FastAPI Server**: REST API and WebSocket distribution

All services are connected via internal Docker networking with automatic health checks and restart policies.
