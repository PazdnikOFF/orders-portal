#!/usr/bin/env bash
# =============================================================================
# fix_botnor_backup.sh — починить опечатку «Ботнер»/«botner» внутри .dump-файла.
#
# Бэкап портала создаётся pg_dump в custom-формате (бинарный) — sed по нему
# напрямую сломает контрольные суммы. Скрипт делает это правильно:
#   1) распаковывает <input>.dump в plain SQL;
#   2) меняет «botner»→«botnor» и «Ботнер»→«Ботнор»;
#   3) собирает обратно в custom-формат, готовый для pg_restore.
#
# Требует, чтобы Docker-стек портала был запущен (`docker compose up -d`) —
# скрипт использует контейнеры db (postgres-tools) и web (доступ к /data/backups).
#
# Использование:
#   /opt/orders-portal/deploy/fix_botnor_backup.sh portal-2026-06-07-153000.dump
#       -> рядом появится portal-2026-06-07-153000.fixed.dump
#
#   /opt/orders-portal/deploy/fix_botnor_backup.sh /полный/путь/файла.dump out.dump
#
# Запускать на сервере под root из любой папки.
# =============================================================================
set -euo pipefail

INPUT="${1:?Укажи имя файла в /data/backups, либо абсолютный путь}"
OUTPUT="${2:-}"

# 0) Определяем папку проекта (где docker-compose.yml)
PROJECT_DIR="${PROJECT_DIR:-/opt/orders-portal}"
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "Не нахожу docker-compose.yml в $PROJECT_DIR" >&2
    exit 1
fi
cd "$PROJECT_DIR"

# 1) Источник в контейнере db
if [[ "$INPUT" == /* ]]; then
    HOST_INPUT="$INPUT"
    BASENAME="$(basename "$INPUT")"
else
    HOST_INPUT=""
    BASENAME="$INPUT"
fi

if [ -z "$OUTPUT" ]; then
    OUTPUT="${BASENAME%.dump}.fixed.dump"
fi
echo ">> Источник:  ${HOST_INPUT:-/data/backups/$BASENAME}"
echo ">> Результат: /data/backups/$OUTPUT"

# 2) Если файл лежит не в томе backups — копируем во временный путь web-контейнера
if [ -n "$HOST_INPUT" ] && [ ! -f "$HOST_INPUT" ]; then
    echo "Файл не найден на хосте: $HOST_INPUT" >&2
    exit 1
fi

DOCKER="docker compose"

# 3) Конвертация в plain SQL (через контейнер web, у которого есть pg_*)
WORK="/tmp/fix_botnor"
$DOCKER exec -T web bash -c "mkdir -p $WORK"

if [ -n "$HOST_INPUT" ]; then
    $DOCKER cp "$HOST_INPUT" web:"$WORK/in.dump"
else
    $DOCKER exec -T web cp "/data/backups/$BASENAME" "$WORK/in.dump"
fi

echo ">> Распаковываю в SQL…"
$DOCKER exec -T web bash -c "pg_restore -f $WORK/in.sql $WORK/in.dump"

echo ">> Замена botner → botnor, Ботнер → Ботнор…"
$DOCKER exec -T web bash -c "
    LC_ALL=C.UTF-8 sed -i \
        -e 's/botner/botnor/g' \
        -e 's/Ботнер/Ботнор/g' \
        $WORK/in.sql
"

# 4) Сборка обратно в custom-формат
#    Чтобы pg_dump смог собрать custom-формат, мы заливаем SQL в одноразовую
#    БД tmp_fix, дампим её обратно и сносим.
echo ">> Сборка нового custom-format дампа…"
$DOCKER exec -T web bash -c '
    set -e
    export PGPASSWORD="${POSTGRES_PASSWORD}"
    psql -h db -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 \
        -c "DROP DATABASE IF EXISTS tmp_fix;" \
        -c "CREATE DATABASE tmp_fix TEMPLATE template0;"
    psql -h db -U "${POSTGRES_USER}" -d tmp_fix -v ON_ERROR_STOP=1 -f '"$WORK"'/in.sql >/dev/null
    pg_dump -h db -U "${POSTGRES_USER}" -Fc -f '"$WORK"'/out.dump tmp_fix
    psql -h db -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE tmp_fix;"
'

# 5) Копируем результат в том backups
$DOCKER exec -T web cp "$WORK/out.dump" "/data/backups/$OUTPUT"
$DOCKER exec -T web rm -rf "$WORK"

echo
echo "✓ Готово."
echo "  В томе backups лежит:           /data/backups/$OUTPUT"
echo "  На хосте это:                   /var/lib/docker/volumes/orders-portal_backups/_data/$OUTPUT"
echo
echo "Восстановить из исправленной копии (заменит текущую базу!):"
echo "  docker compose exec db bash -c 'pg_restore --clean --if-exists --no-owner -h db -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" /data/backups/$OUTPUT'"
