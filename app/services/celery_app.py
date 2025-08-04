from celery import Celery
from app.core.config import settings

# Create Celery app instance with 'app' as the main module name
celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.services.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_ignore_result=True,  # Fire-and-forget tasks for better performance
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks configuration (beat_schedule)
celery_app.conf.beat_schedule = {
    "discover-traders": {
        "task": "app.services.tasks.task_discover_traders",
        "schedule": 15.0 * 60,  # Every 15 minutes
    },
    "track-traders": {
        "task": "app.services.tasks.task_track_traders",
        "schedule": 60.0,  # Every 1 minute
    },
    "calculate-leaderboard": {
        "task": "app.services.tasks.task_calculate_leaderboard",
        "schedule": 60.0 * 60,  # Every 1 hour
    },
}
