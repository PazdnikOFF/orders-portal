# Механизм резервного копирования

## Принципы (ТЗ §5)

- Резервная копия БД создаётся **автоматически каждые 3 часа**.
- Копирование выполняется «на лету», без остановки портала (`pg_dump`).
- Срок хранения копий — **90 дней**; старше — удаляются автоматически.
- Доступ к модулю резервных копий — только у роли **Админ**.
- Все операции журналируются.

## Как это работает

| Компонент | Назначение |
|---|---|
| `apps/backups/services.py` | движок: `run_backup`, `run_restore`, `delete_backup`, `prune_old_backups` |
| `apps/backups/tasks.py` | Celery-задачи `create_backup`, `prune_old_backups` |
| `config/celery.py` | расписание: бэкап каждые `BACKUP_INTERVAL_HOURS` ч, очистка ежедневно |
| контейнер `beat` | планировщик Celery Beat |
| контейнер `worker` | исполняет задачи |

Копии создаются командой `pg_dump -Fc` (custom format) и складываются в том
`backups` (`/data/backups`). Каталог копий хранится в таблице `backups_backup`.

Образ приложения содержит **postgresql-client-16**, совместимый с сервером
PostgreSQL 16.

## Модуль в интерфейсе

Меню **Резервные копии** (только администратор):

- список копий с датой/временем создания, типом и статусом;
- **Создать копию сейчас** — ручной запуск;
- **Восстановить** — восстановление БД из выбранной копии (см.
  [restore.md](restore.md));
- **Удалить** — удаление выбранной копии.

## Настройки (`.env`)

```
BACKUP_ROOT=/data/backups
BACKUP_RETENTION_DAYS=90
BACKUP_INTERVAL_HOURS=3
```

## Ручной бэкап из консоли

```bash
# через Celery-движок (с записью в каталог копий)
docker compose exec web python manage.py shell -c \
  "from apps.backups.services import run_backup; print(run_backup(kind='manual').filename)"

# либо «сырой» дамп файла
docker compose exec db pg_dump -Fc -U portal portal > portal_$(date +%F).dump
```

## Хранение копий вне сервера

Том `backups` рекомендуется периодически копировать на внешнее хранилище
(например, тем же rclone — см. [google_drive.md](google_drive.md)) или
средствами резервного копирования инфраструктуры.
