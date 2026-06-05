# Настройка синхронизации с Google Drive (rclone)

Папка с файлами заказов (`/data/orders`) синхронизируется с Google Drive с
помощью **rclone** по расписанию. По умолчанию синхронизация выключена.

## 1. Получить токен Google Drive (rclone)

На любой машине с rclone и браузером:

```bash
rclone config
# n) New remote
# name> gdrive           (имя должно совпадать с RCLONE_REMOTE без пути)
# Storage> drive         (Google Drive)
# client_id / client_secret — можно оставить пустыми (или указать свои OAuth)
# scope> 1               (полный доступ) или 2 (drive.file)
# Auto config> Yes — пройдите авторизацию в браузере
```

В результате в `~/.config/rclone/rclone.conf` появится секция `[gdrive]`.

## 2. Разместить конфиг на сервере

Скопируйте `rclone.conf` в каталог, указанный в `RCLONE_CONFIG_DIR`
(по умолчанию `./deploy/rclone`):

```bash
cp rclone.conf /opt/orders-portal/deploy/rclone/rclone.conf
```

Контейнер `worker` монтирует этот каталог только для чтения в
`/home/app/.config/rclone`.

## 3. Включить синхронизацию в `.env`

```
RCLONE_ENABLED=True
RCLONE_REMOTE=gdrive:orders          # remote:папка_назначения
RCLONE_SYNC_INTERVAL_MINUTES=30
RCLONE_CONFIG_DIR=./deploy/rclone
```

Перезапустите стек:

```bash
docker compose up -d
```

## 4. Как это работает

- Celery Beat каждые `RCLONE_SYNC_INTERVAL_MINUTES` запускает задачу
  `apps.integrations.tasks.sync_files_to_drive`.
- Задача выполняет `rclone sync /data/orders <RCLONE_REMOTE>` — односторонняя
  синхронизация (локальная папка → Google Drive).
- Файлы хранятся **без шифрования**, имя файла соответствует номеру заказа.

## 5. Проверка вручную

```bash
docker compose exec worker rclone listremotes
docker compose exec worker rclone ls gdrive:orders
docker compose exec worker python manage.py shell -c \
  "from apps.integrations.tasks import sync_files_to_drive; print(sync_files_to_drive())"
```

## 6. Замечания

- Для двусторонней синхронизации или резервного копирования бэкапов можно
  добавить аналогичную задачу/команду (`rclone sync /data/backups gdrive:backups`).
- Синхронизация — отдельный, изолированный модуль; её отключение
  (`RCLONE_ENABLED=False`) не влияет на работу портала.
