"""
Celery application entrypoint. Import this in config/__init__.py so Django
picks up the Celery app whenever it starts (`python manage.py runserver`,
`python manage.py shell`, etc. all trigger this import).

Run a worker with:
    celery -A config worker --loglevel=info --pool=solo   # --pool=solo needed on Windows

Run Redis (the broker) with Docker (simplest cross-platform option):
    docker run -p 6379:6379 redis

Or natively on Windows via WSL, or via a Windows Redis port like Memurai.
See README "Priority 7" for the full walkthrough.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("shopify_taxonomy_classifier")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
