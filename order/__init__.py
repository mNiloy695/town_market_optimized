# Ensure Celery app is loaded when Django starts
# This ensures shared_task decorators work properly
from core.celery import app as celery_app

__all__ = ('celery_app',)