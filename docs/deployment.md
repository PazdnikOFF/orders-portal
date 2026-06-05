# Инструкция по развёртыванию

Портал разворачивается как изолированный Docker-стек на том же сервере CentOS,
где работает Bitrix24, **не мешая** основному порталу.

## 1. Принцип изоляции от Bitrix24

- Все сервисы портала (app, PostgreSQL, Redis, worker, beat, nginx) работают в
  собственной Docker-сети `orders-portal_internal`.
- Используются **отдельные** контейнеры PostgreSQL и Redis — БД и сервисы
  Bitrix24 не затрагиваются.
- Наружу публикуется **только один порт** — nginx портала (`HTTP_PORT`, по
  умолчанию `8080`). Порты 80/443, занятые Bitrix24, не используются.
- Данные хранятся в именованных Docker-томах и переживают пересборку образа.

## 2. Требования к серверу

- CentOS 7/8/9 (или другой Linux) с установленным Docker Engine ≥ 24 и
  плагином `docker compose` v2.
- Свободный TCP-порт для портала (по умолчанию 8080).
- 2+ ГБ свободной памяти, 10+ ГБ диска под данные/файлы/бэкапы.

Проверка:

```bash
docker --version
docker compose version
```

## 3. Установка

```bash
# 1. Скопировать каталог проекта на сервер, например в /opt/orders-portal
cd /opt/orders-portal

# 2. Создать конфигурацию из шаблона
cp .env.example .env

# 3. Отредактировать .env (обязательно изменить):
#    SECRET_KEY            — длинная случайная строка
#    POSTGRES_PASSWORD     — надёжный пароль БД
#    ADMIN_PASSWORD        — пароль первичного администратора
#    ALLOWED_HOSTS         — доменное имя/адрес портала
#    CSRF_TRUSTED_ORIGINS  — полный origin (https://orders.example.com)
#    HTTP_PORT             — внешний порт (не 80/443)
nano .env

# 4. Сборка и запуск
docker compose up -d --build

# 5. Проверка
docker compose ps
docker compose logs -f web
```

Генерация `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 4. Что происходит при первом старте

Контейнер `web` (entrypoint `web`) автоматически:

1. дожидается готовности PostgreSQL;
2. применяет миграции (`migrate`);
3. собирает статику (`collectstatic`);
4. создаёт администратора из `ADMIN_USERNAME`/`ADMIN_PASSWORD` (если его нет);
5. запускает gunicorn на `:8000` (за nginx).

Контейнеры `worker` и `beat` поднимают Celery для фоновых задач (бэкапы,
очистка, синхронизация Google Drive).

## 5. Внешний доступ и HTTPS

nginx портала слушает порт `HTTP_PORT` по HTTP. Рекомендуется публиковать портал
через внешний reverse-proxy (например, отдельный server-блок Apache/nginx
Bitrix-хоста или внешний балансировщик) с TLS, проксируя на
`http://127.0.0.1:8080`.

При работе за HTTPS-прокси в `.env` задайте:

```
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://orders.example.com
```

Заголовок `X-Forwarded-Proto` уже учитывается приложением.

## 6. Обновление версии

```bash
git pull            # или скопировать новую версию кода
docker compose build
docker compose up -d
```

Миграции применяются автоматически при старте `web`. Тома с данными
сохраняются.

## 7. Управление

```bash
docker compose ps                     # статус
docker compose logs -f web worker     # логи
docker compose restart web            # перезапуск
docker compose down                   # остановка (тома сохраняются)
docker compose exec web python manage.py createsuperuser   # доп. админ
```

## 8. Резервное копирование при остановке

Тома `pgdata`, `order_files`, `backups` содержат все данные. Перед обновлением
сервера или Docker сделайте резервную копию (см. [backup.md](backup.md)).
