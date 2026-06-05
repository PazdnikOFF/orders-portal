# Order Tracking Portal — application image.
# Single image runs as web / celery worker / celery beat (selected by entrypoint).
# Pinned to bookworm so the bookworm PGDG repo (postgresql-client-16) matches the
# base distro. Plain python:3.12-slim now tracks Debian trixie and conflicts.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# System deps:
#  - postgresql-client-16: pg_dump / pg_restore / pg_isready (backup module, TЗ §5)
#  - rclone: Google Drive sync (TЗ §6)
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates rclone \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-16 \
 && apt-get purge -y curl gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY app/ /app/
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && adduser --system --group app \
 && mkdir -p /data/orders /data/backups /app/staticfiles \
 && chown -R app:app /app /data

USER app
ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
