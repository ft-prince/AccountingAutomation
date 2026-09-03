import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("nexren")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {}  # later phases add entries


@app.task(bind=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    return f"ok:{self.request.id}"
