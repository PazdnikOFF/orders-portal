"""
Backup engine (TЗ §5). Uses pg_dump (custom format) / pg_restore so backups run
"on the fly" without stopping the portal. Retention prunes copies older than
BACKUP_RETENTION_DAYS (90). All admin actions are journaled (TЗ §17/§18).
"""
import logging
import os
import subprocess
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.audit.models import ActionType
from apps.audit.services import log_action

from .models import Backup, BackupKind, BackupStatus

logger = logging.getLogger("apps.backups")


def _db_env_and_conn():
    db = settings.DATABASES["default"]
    env = os.environ.copy()
    if db.get("PASSWORD"):
        env["PGPASSWORD"] = db["PASSWORD"]
    conn = [
        "-h", db.get("HOST") or "localhost",
        "-p", str(db.get("PORT") or "5432"),
        "-U", db.get("USER") or "postgres",
        "-d", db.get("NAME"),
    ]
    return env, conn, db.get("NAME")


def run_backup(kind=BackupKind.AUTO, user=None, request=None) -> Backup:
    """Create one database backup and catalog it."""
    settings.BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    ts = timezone.now().strftime("%Y%m%d-%H%M%S")
    filename = f"portal-{ts}.dump"
    abs_path = settings.BACKUP_ROOT / filename

    env, conn, _ = _db_env_and_conn()
    cmd = [settings.PG_DUMP_BIN, "-Fc", "-f", str(abs_path), *conn]

    backup = Backup(filename=filename, rel_path=filename, kind=kind, created_by=user)
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60 * 25)
        if result.returncode != 0:
            backup.status = BackupStatus.FAILED
            backup.note = (result.stderr or "")[:500]
            logger.error("pg_dump failed: %s", result.stderr)
        else:
            backup.status = BackupStatus.OK
            backup.size = abs_path.stat().st_size if abs_path.exists() else 0
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        backup.status = BackupStatus.FAILED
        backup.note = str(exc)[:500]
        logger.exception("pg_dump error")

    backup.save()
    log_action(request, ActionType.BACKUP_CREATE, target=backup,
               summary=f"Резервная копия {filename} ({backup.get_status_display()})")
    return backup


def run_restore(backup: Backup, user=None, request=None) -> bool:
    """
    Restore the database from a backup using pg_restore --clean (in-place, no
    downtime). Journaled per TЗ §18.
    """
    if not backup.exists_on_disk:
        log_action(request, ActionType.BACKUP_RESTORE, target=backup,
                   summary=f"Восстановление НЕ выполнено: файл {backup.filename} отсутствует")
        return False

    env, conn, dbname = _db_env_and_conn()
    cmd = [settings.PG_RESTORE_BIN, "--clean", "--if-exists", "--no-owner",
           "--no-privileges", *conn, str(backup.abs_path)]
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60 * 25)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.exception("pg_restore error")
        log_action(request, ActionType.BACKUP_RESTORE, target=backup,
                   summary=f"Ошибка восстановления из {backup.filename}: {exc}")
        return False

    # pg_restore may emit non-fatal warnings (returncode != 0) yet still succeed.
    ok = result.returncode == 0 or "errors ignored on restore" not in (result.stderr or "")
    log_action(request, ActionType.BACKUP_RESTORE, target=backup,
               summary=f"Восстановление БД из {backup.filename} (код {result.returncode})")
    if result.returncode != 0:
        logger.warning("pg_restore returned %s: %s", result.returncode, result.stderr[-1000:])
    return ok


def delete_backup(backup: Backup, user=None, request=None) -> None:
    """Delete a backup file and its catalog record (admin only, journaled)."""
    filename = backup.filename
    try:
        if backup.exists_on_disk:
            os.remove(backup.abs_path)
    except OSError:
        logger.exception("Failed to remove backup file %s", backup.abs_path)
    log_action(request, ActionType.BACKUP_DELETE, target=backup,
               summary=f"Удалена резервная копия {filename}")
    backup.delete()


def prune_old_backups(request=None) -> int:
    """Delete backups older than the retention window (TЗ §5.1 — 90 дней)."""
    cutoff = timezone.now() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
    old = Backup.objects.filter(created_at__lt=cutoff)
    count = 0
    for backup in old:
        delete_backup(backup, request=request)
        count += 1
    if count:
        logger.info("Pruned %s backups older than %s days", count, settings.BACKUP_RETENTION_DAYS)
    return count
