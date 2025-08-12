# Docker Database Initialization Script (PowerShell)

Write-Host "🔄 Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow

# Wait for PostgreSQL to be ready
do {
    $result = docker-compose exec postgres pg_isready -U hyperliquid_user -d hyperliquid_db 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "PostgreSQL is unavailable - sleeping" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
} while ($LASTEXITCODE -ne 0)

Write-Host "✅ PostgreSQL is ready!" -ForegroundColor Green

# Run database initialization
Write-Host "🔄 Initializing database tables..." -ForegroundColor Yellow
docker-compose exec fastapi-server python init_db.py

Write-Host "✅ Database initialization complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🚀 Your Hyperliquid Copy Trading Platform is now running!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access points:" -ForegroundColor White
Write-Host "  • API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  • Health Check: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host "  • Leaderboard: http://localhost:8000/api/v1/leaderboard" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service status:" -ForegroundColor White
Write-Host "  • Discovery Service: docker-compose logs discovery-service" -ForegroundColor Gray
Write-Host "  • Celery Worker: docker-compose logs celery-worker" -ForegroundColor Gray
Write-Host "  • Celery Beat: docker-compose logs celery-beat" -ForegroundColor Gray
Write-Host "  • FastAPI Server: docker-compose logs fastapi-server" -ForegroundColor Gray
