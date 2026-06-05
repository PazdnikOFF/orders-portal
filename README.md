# Портал учёта и сопровождения заказов

Веб-портал для учёта, просмотра, редактирования и сопровождения заказов со
строгой ролевой моделью, историей изменений, журналом действий, файловым
хранилищем и автоматическим резервным копированием.

Разработан под развёртывание в Docker на выделенном сервере **CentOS рядом с
Bitrix24**: собственные контейнеры PostgreSQL/Redis, изолированная сеть, наружу
публикуется только один порт reverse-proxy (по умолчанию `8080`, не 80/443).

## Технологический стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework |
| Основная БД | PostgreSQL 16 |
| Сессии / кэш / брокер | Redis 7 |
| Фоновые задачи | Celery + Celery Beat |
| Frontend | Серверный рендеринг + HTMX + Alpine.js + SortableJS (без Node) |
| Файлы | Локальная папка + синхронизация Google Drive (rclone) |
| Запуск | Docker / docker-compose, nginx, gunicorn |

## Структура репозитория

```
Site/
├── app/                      # Django-приложение
│   ├── config/               # settings, urls, api, celery, wsgi/asgi
│   └── apps/
│       ├── accounts/         # пользователи, роли, сессии (45 мин), права
│       ├── directories/      # сотрудники, организации (поиск по ИНН)
│       ├── orders/           # заказы, нумерация, матрица прав, история
│       ├── files/            # файлы заказа, soft-delete, защищённая выдача
│       ├── backups/          # резервные копии (pg_dump/pg_restore)
│       ├── audit/            # журнал действий
│       └── integrations/     # провайдер ИНН (DaData/stub), rclone-sync
├── deploy/                   # nginx, entrypoint, rclone-конфиг
├── docs/                     # документация (см. ниже)
├── Dockerfile, docker-compose.yml, .env.example
```

## Быстрый старт

```bash
cp .env.example .env          # заполните секреты (SECRET_KEY, пароли, ADMIN_PASSWORD)
docker compose up -d --build  # сборка и запуск всех сервисов
```

Портал будет доступен на `http://<host>:8080/`. Первичный администратор
создаётся автоматически из `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## Документация

| Документ | Назначение |
|---|---|
| [docs/deployment.md](docs/deployment.md) | Развёртывание на сервере с Bitrix24 |
| [docs/admin_guide.md](docs/admin_guide.md) | Инструкция администратора |
| [docs/user_guide.md](docs/user_guide.md) | Инструкция пользователя |
| [docs/database.md](docs/database.md) | Структура базы данных |
| [docs/backup.md](docs/backup.md) | Механизм резервного копирования |
| [docs/restore.md](docs/restore.md) | Восстановление из резервной копии |
| [docs/google_drive.md](docs/google_drive.md) | Настройка синхронизации с Google Drive |
| [docs/api.md](docs/api.md) | REST API |

## Ролевая модель (кратко)

| Возможность | Админ | Оператор | Менеджер | Руководитель |
|---|:--:|:--:|:--:|:--:|
| Просмотр всех записей | ✅ | ✅ | только свои | ✅ |
| Создание записей | ✅ | ✅ | ❌ | ❌ |
| Редактирование (по матрице стадий) | ✅ (полный) | ✅ | ❌ | ❌ |
| Смена статуса | ✅ | ✅ | ❌ | ❌ |
| Загрузка/удаление файлов | ✅ | ✅ | ❌ | ❌ |
| Управление пользователями | ✅ | ❌ | ❌ | ❌ |
| Резервные копии | ✅ | ❌ | ❌ | ❌ |

Полная матрица редактирования полей по стадиям — в
[app/apps/orders/matrix.py](app/apps/orders/matrix.py) и
[docs/admin_guide.md](docs/admin_guide.md).
