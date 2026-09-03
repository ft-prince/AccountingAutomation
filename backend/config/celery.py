import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("nexren")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "refresh-overdue-nightly": {
        "task": "apps.payments.tasks.refresh_overdue_statuses",
        "schedule": crontab(hour=1, minute=0),
    },
}


@app.task(bind=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    return f"ok:{self.request.id}"
