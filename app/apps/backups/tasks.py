"""Celery wrappers around the backup engine (scheduled in config/celery.py)."""
from celery import shared_task

from .models import BackupKind
from .services import prune_old_backups as _prune
from .services import run_backup


@shared_task(name="apps.backups.tasks.create_backup")
def create_backup(kind: str = BackupKind.AUTO):
    backup = run_backup(kind=kind)
    return {"id": backup.id, "filename": backup.filename, "status": backup.status}


@shared_task(name="apps.backups.tasks.prune_old_backups")
def prune_old_backups():
    return {"pruned": _prune()}
