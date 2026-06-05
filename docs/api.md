# REST API

REST API доступно по префиксу `/api/v1/`. Все запросы требуют авторизации
(сессия портала). Используется session-аутентификация Django; для POST/PUT
необходим CSRF-токен.

Видимость данных и права полностью соответствуют ролевой модели портала
(менеджер видит только свои заказы, изменения проходят серверную проверку прав
и матрицу стадий).

## Заказы

| Метод | Endpoint | Описание |
|---|---|---|
| GET | `/api/v1/orders/` | список заказов (с учётом роли), пагинация |
| GET | `/api/v1/orders/{id}/` | карточка заказа |
| POST | `/api/v1/orders/` | создание заказа |
| PUT/PATCH | `/api/v1/orders/{id}/` | изменение (по матрице стадий) |
| POST | `/api/v1/orders/{id}/status/` | смена статуса |

### Создание заказа (POST `/api/v1/orders/`)

```json
{
  "manager": 1,
  "distributor_inn": "7700000001",
  "potential_user_inn": "7700000002",
  "participant_inns": ["7700000003"],
  "kit": "Комплект A",
  "forecast_date": "2026-12-31",
  "status": "planned"
}
```

Организации подгружаются по ИНН и сохраняются в справочник автоматически.
`order_number`, `request_date` присваиваются системой.

### Ответ (чтение)

```json
{
  "id": 1,
  "order_number": 1,
  "order_code": "ORD-000001",
  "manager": "Иванов Иван",
  "distributor": "ООО «Ромашка» (7700000001)",
  "potential_user": "ООО «Тест» (7700000002)",
  "participants": ["ООО «Пример» (7700000003)"],
  "kit": "Комплект A",
  "request_date": "2026-06-05",
  "forecast_date": "2026-12-31",
  "status": "planned",
  "status_display": "В плане",
  "file_url": "http://host/files/serve/1/",
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

### Смена статуса

`POST /api/v1/orders/{id}/status/` → `{"status": "in_progress"}`

## Справочники

| Метод | Endpoint | Описание |
|---|---|---|
| GET | `/api/v1/employees/?type=manager&active=1` | сотрудники |
| GET | `/api/v1/organizations/` | организации |
| POST | `/api/v1/organizations/lookup/` | поиск по ИНН: `{"inn": "..."}` |

## Файлы

Загрузка/просмотр файлов выполняется через основной интерфейс:

| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/files/upload/{order_id}/` | загрузка (multipart, поле `file`) |
| POST | `/files/detach/{file_id}/` | открепить от карточки (soft-delete) |
| GET | `/files/serve/{file_id}/` | защищённый просмотр файла |

## Коды ответов

- `401/302` — не авторизован;
- `403` — недостаточно прав или запрещено стадией/ролью;
- `422` — организация по ИНН не найдена / ошибка провайдера;
- `400` — ошибка валидации.
