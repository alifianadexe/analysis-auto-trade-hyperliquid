#!/usr/bin/env python3
"""
Celery worker startup script for the Hyperliquid Auto Trade application.
"""

from app.services.celery_app import celery_app

if __name__ == "__main__":
    celery_app.start()
