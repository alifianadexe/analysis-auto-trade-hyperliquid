"""
Celery tasks package for the auto-trade-hyperliquid application.

This package contains all the background tasks organized by functionality:
- discovery_task.py: WebSocket trader discovery
- tracking_task.py: Trader position tracking
- leaderboard_task.py: Leaderboard calculation and scoring
- utils.py: Shared utilities and helper functions
"""

# Import all tasks to make them available when the package is imported
from .discovery_task import task_manage_discovery_stream
from .tracking_task import task_track_traders_batch
from .leaderboard_task import task_calculate_leaderboard

__all__ = [
    "task_manage_discovery_stream",
    "task_track_traders_batch", 
    "task_calculate_leaderboard"
]
