import os

from celery import Celery

# point Celery at the Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
# read every CELERY_* setting from settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")
# find tasks.py in each installed app
app.autodiscover_tasks()
