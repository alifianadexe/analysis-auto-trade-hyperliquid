"""
Celery tasks package for the auto-trade-hyperliquid application.

This package contains background tasks organized by functionality:
- tracking_task.py: Trader position tracking
- leaderboard_task.py: Leaderboard calculation and scoring
- utils.py: Shared utilities and helper functions

Note: WebSocket trader discovery is now handled by a standalone service
in app.services.discovery_service.py
"""

# Import all tasks to make them available when the package is imported
from .tracking_task import task_track_traders_batch
from .leaderboard_task import task_calculate_leaderboard

__all__ = [
    "task_track_traders_batch", 
    "task_calculate_leaderboard"
]
