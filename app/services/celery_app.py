from celery import Celery
from app.core.config import settings

# Create Celery app instance with 'app' as the main module name
# Note: discovery_task removed as it runs as standalone WebSocket service
celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.services.tasks.tracking_task", 
        "app.services.tasks.leaderboard_task"
    ]
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
    worker_max_tasks_per_child=1000
)

# Periodic tasks configuration (beat_schedule) - WebSocket discovery now runs standalone
celery_app.conf.beat_schedule = {
    "track-traders-batch": {
        "task": "app.services.tasks.tracking_task.task_track_traders_batch",
        "schedule": 75.0,  # Every 75 seconds (safe rate limiting: configurable BATCH_SIZE * 20 weight)
    },
    "calculate-leaderboard": {
        "task": "app.services.tasks.leaderboard_task.task_calculate_leaderboard",
        "schedule": 10.0 * 60,  # Every 10 minutes
    },
}
