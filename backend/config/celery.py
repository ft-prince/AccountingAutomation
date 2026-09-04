import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("nexren")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "purge-deleted-orgs-nightly": {
        "task": "apps.accounts.tasks.purge_deleted_orgs",
        "schedule": crontab(hour=2, minute=0),
    },
    "send-due-reports-daily": {
        "task": "apps.reporting.tasks.send_due_reports",
        "schedule": crontab(hour=6, minute=30),
    },
    "refresh-overdue-nightly": {
        "task": "apps.payments.tasks.refresh_overdue_statuses",
        "schedule": crontab(hour=1, minute=0),
    },
    "sync-all-mailboxes": {
        "task": "apps.mail.tasks.sync_all_mailboxes",
        "schedule": 120.0,  # PROJECT_SPECS §6.3: poll every 2 minutes
    },
    "forecast-nightly": {
        "task": "apps.forecasting.tasks.run_nightly_forecasts",
        "schedule": crontab(hour=3, minute=0),  # PROJECT_SPECS §8.7, after overdue refresh
    },
    "database-backup-nightly": {
        "task": "apps.accounts.tasks.run_database_backup",
        "schedule": crontab(hour=4, minute=15),  # quiet hour, clear of purge/forecast/reports
    },
    "check-backup-freshness": {
        "task": "apps.accounts.tasks.check_backup_freshness",
        "schedule": crontab(hour="*/6", minute=20),
    },
}


@app.task(bind=True)
def debug_task(self) -> str:  # type: ignore[no-untyped-def]
    return f"ok:{self.request.id}"
