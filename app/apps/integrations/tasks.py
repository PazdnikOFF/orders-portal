"""Background integration tasks — Google Drive sync via rclone (TЗ §6)."""
import logging
import subprocess

from celery import shared_task
from django.conf import settings

logger = logging.getLogger("apps.integrations")


@shared_task(name="apps.integrations.tasks.sync_files_to_drive")
def sync_files_to_drive():
    """
    One-way sync of the order-files folder to Google Drive using rclone.
    Pluggable: disabled by default (RCLONE_ENABLED). The rclone config/token is
    mounted into the worker container; no secrets live in the codebase.
    """
    if not settings.RCLONE_ENABLED:
        logger.info("rclone sync skipped (RCLONE_ENABLED=False)")
        return {"status": "skipped"}

    source = str(settings.ORDER_FILES_ROOT)
    cmd = [settings.RCLONE_BIN, "sync", source, settings.RCLONE_REMOTE, "--create-empty-src-dirs"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.error("rclone sync failed to start: %s", exc)
        return {"status": "error", "detail": str(exc)}

    if result.returncode != 0:
        logger.error("rclone sync error (%s): %s", result.returncode, result.stderr)
        return {"status": "error", "returncode": result.returncode, "stderr": result.stderr[-2000:]}

    logger.info("rclone sync OK: %s -> %s", source, settings.RCLONE_REMOTE)
    return {"status": "ok"}
