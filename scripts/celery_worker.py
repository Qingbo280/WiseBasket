"""Celery worker entrypoint aggregating all task modules.

Railway startCommand:
    celery -A scripts.celery_worker:celery_app worker --loglevel=INFO --beat \
        --scheduler celery.beat:PersistentScheduler --schedule-filename /tmp/celerybeat-schedule

Importing a task module here registers its tasks on the shared celery_app
defined in scripts.daily_pricecatcher_update (None when REDIS_URL is unset).
"""
from __future__ import annotations

from scripts.daily_pricecatcher_update import celery_app  # noqa: F401
import scripts.receipt_tasks  # noqa: F401  (registers extract_receipt_task)
