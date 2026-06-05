"""Celery application + periodic schedule (backups, retention, rclone sync)."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("portal")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from django.conf import settings

    # Automatic database backup every N hours (TЗ §5.1 — каждые 3 часа).
    sender.add_periodic_task(
        crontab(minute=0, hour=f"*/{settings.BACKUP_INTERVAL_HOURS}"),
        app.signature("apps.backups.tasks.create_backup", kwargs={"kind": "auto"}),
        name="auto-backup-every-N-hours",
    )
    # Daily retention sweep — delete backups older than 90 days (TЗ §5.1).
    sender.add_periodic_task(
        crontab(minute=30, hour=2),
        app.signature("apps.backups.tasks.prune_old_backups"),
        name="prune-old-backups-daily",
    )
    # Periodic Google Drive sync via rclone (only when enabled).
    if settings.RCLONE_ENABLED:
        sender.add_periodic_task(
            settings.RCLONE_SYNC_INTERVAL_MINUTES * 60.0,
            app.signature("apps.integrations.tasks.sync_files_to_drive"),
            name="rclone-gdrive-sync",
        )
