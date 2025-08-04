# Makefile for Hyperliquid Auto Trade

.PHONY: help install dev-setup run worker beat test clean docker-up docker-down

# Default target
help:
	@echo "Available commands:"
	@echo "  install      Install Python dependencies"
	@echo "  dev-setup    Set up development environment"
	@echo "  run          Start the FastAPI server"
	@echo "  worker       Start Celery worker"
	@echo "  beat         Start Celery beat scheduler"
	@echo "  test         Run tests"
	@echo "  clean        Clean up temporary files"
	@echo "  docker-up    Start PostgreSQL and Redis containers"
	@echo "  docker-down  Stop PostgreSQL and Redis containers"

# Install dependencies
install:
	pip install -r requirements.txt

# Set up development environment
dev-setup:
	python -m venv .venv
	.venv/Scripts/activate && pip install -r requirements.txt
	cp .env.example .env
	@echo "Development environment setup complete!"
	@echo "Please update the .env file with your configuration."

# Start FastAPI server
run:
	python run.py

# Start Celery worker
worker:
	celery -A app.services.celery_app worker --loglevel=info

# Start Celery beat scheduler
beat:
	celery -A app.services.celery_app beat --loglevel=info

# Run tests (to be implemented)
test:
	@echo "Tests not implemented yet"

# Clean up temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +

# Start Docker services
docker-up:
	docker-compose up -d

# Stop Docker services
docker-down:
	docker-compose down
