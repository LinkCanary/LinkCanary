"""Celery application configuration (optional, for production use)."""

from ..config import settings

celery_app = None

if settings.use_celery:
    try:
        from celery import Celery
        
        celery_app = Celery(
            "linkcanary",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
            include=["backend.tasks.crawl_task"],
        )
        
        celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=3600,
            task_soft_time_limit=3500,
            worker_prefetch_multiplier=1,
            task_acks_late=True,
        )
    except ImportError:
        pass
