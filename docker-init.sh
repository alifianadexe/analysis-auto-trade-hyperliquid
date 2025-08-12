#!/bin/bash
# Docker Database Initialization Script

echo "🔄 Waiting for PostgreSQL to be ready..."

# Wait for PostgreSQL to be ready
until docker-compose exec postgres pg_isready -U hyperliquid_user -d hyperliquid_db; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Run database initialization
echo "🔄 Initializing database tables..."
docker-compose exec fastapi-server python init_db.py

echo "✅ Database initialization complete!"
echo ""
echo "🚀 Your Hyperliquid Copy Trading Platform is now running!"
echo ""
echo "Access points:"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/health"
echo "  • Leaderboard: http://localhost:8000/api/v1/leaderboard"
echo ""
echo "Service status:"
echo "  • Discovery Service: docker-compose logs discovery-service"
echo "  • Celery Worker: docker-compose logs celery-worker"
echo "  • Celery Beat: docker-compose logs celery-beat"
echo "  • FastAPI Server: docker-compose logs fastapi-server"
