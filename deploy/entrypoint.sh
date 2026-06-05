#!/usr/bin/env bash
# Entrypoint dispatcher. Usage: entrypoint.sh [web|worker|beat|<command>]
set -e

ROLE="${1:-web}"
PGPORT="${POSTGRES_PORT:-5432}"

wait_for_db() {
  echo "Ожидание PostgreSQL на ${POSTGRES_HOST}:${PGPORT}..."
  until pg_isready -h "${POSTGRES_HOST}" -p "${PGPORT}" -U "${POSTGRES_USER}" >/dev/null 2>&1; do
    sleep 1
  done
  echo "PostgreSQL доступен."
}

case "${ROLE}" in
  web)
    wait_for_db
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    python manage.py ensure_admin
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout 120 \
        --access-logfile - --error-logfile -
    ;;
  worker)
    wait_for_db
    exec celery -A config worker -l "${CELERY_LOGLEVEL:-info}" \
        --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  beat)
    wait_for_db
    exec celery -A config beat -l "${CELERY_LOGLEVEL:-info}" \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;
  *)
    exec "$@"
    ;;
esac
