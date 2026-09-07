"""
Celery Application Configuration.

Configures Celery with Redis as the broker.
Defines queues for different task types.
"""

import os

from celery import Celery

# Broker URL
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Create Celery app
app = Celery(
    "pso_traffic_workers",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

# Celery configuration
app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Time limits
    task_soft_time_limit=1500,   # 25 minutes soft
    task_time_limit=1800,        # 30 minutes hard

    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Beat scheduler (periodic tasks)
    beat_schedule={
        "cleanup-old-reports": {
            "task": "workers.tasks.report_tasks.archive_old_reports",
            "schedule": 86400.0,  # Daily
        },
        "health-check": {
            "task": "workers.tasks.cleanup_tasks.health_check",
            "schedule": 300.0,  # Every 5 minutes
        },
        # Phase 5 Step 5.4: nightly model retraining (02:00 UTC)
        "nightly-model-retrain": {
            "task": "workers.tasks.model_tasks.nightly_retrain_task",
            "schedule": 86400.0,
            "options": {"expires": 3600},
        },
    },
)

# Auto-discover tasks
app.autodiscover_tasks(["workers.tasks"])
