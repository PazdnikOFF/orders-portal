# Структура базы данных

Основная БД — **PostgreSQL**. Redis используется только для сессий, кэша
справочников и брокера Celery (не как основное хранилище).

Все даты/время хранятся в **UTC**; в интерфейсе показываются с учётом
`DISPLAY_TIME_ZONE`.

## Перечень сущностей

### accounts_user — Пользователь
| Поле | Тип | Описание |
|---|---|---|
| id | bigint PK | |
| username | varchar unique | логин |
| password | varchar | хеш пароля (Argon2) |
| full_name | varchar | ФИО |
| role | varchar | `admin` / `operator` / `manager` / `director` |
| employee_id | FK→directories_employee | профиль сотрудника (для менеджера) |
| is_active | bool | активность (False = заблокирован) |
| last_login | datetime | дата последнего входа |
| date_joined | datetime | дата создания |

### directories_employee — Сотрудник
| Поле | Тип | Описание |
|---|---|---|
| id | bigint PK | |
| last_name / first_name / middle_name | varchar | Фамилия / Имя / Отчество |
| type | varchar | `manager`/`operator`/`director`/`admin`/`other` |
| is_active | bool | активность |

Отображение в списках — «Фамилия Имя».

### directories_organization — Организация
| Поле | Тип | Описание |
|---|---|---|
| id | bigint PK | |
| inn | varchar unique | ИНН |
| name | varchar | краткое наименование |
| full_name | varchar | полное наименование |
| kpp / ogrn | varchar | КПП / ОГРН |
| address | varchar | юридический адрес |
| status | varchar | статус организации |
| source | varchar | источник данных (`dadata`/`stub`) |
| updated_at | datetime | дата последнего обновления |

Отображение — «Наименование (ИНН)». Используется для полей Дистрибьютор,
Потенциальный пользователь и Участники.

### orders_order — Заказ
| Поле | Тип | Описание |
|---|---|---|
| id | bigint PK | |
| order_number | int unique | системный номер (gapless, без пропусков) |
| manager_id | FK→employee | менеджер (PROTECT) |
| distributor_id | FK→organization | дистрибьютор |
| potential_user_id | FK→organization | потенциальный пользователь |
| participants | M2M→organization | участники проекта (Комментарий) |
| kit | varchar | комплект |
| request_date | date | дата обращения (системная, не редактируется) |
| forecast_date | date | прогнозируемая дата реализации |
| status | varchar | `planned`/`in_progress`/`produced`/`cancelled` |
| created_at / updated_at | datetime | даты создания / изменения |
| created_by_id / updated_by_id | FK→user | кто создал / изменил |

### orders_ordersequence — Счётчик номеров
Хранит текущее значение номера заказа. Инкремент выполняется под
`SELECT ... FOR UPDATE` в той же транзакции, что и создание заказа, — это
гарантирует **отсутствие пропусков** и повторов (в отличие от обычной
PostgreSQL-sequence, которая может оставлять пропуски при откате).

### orders_orderhistory — История изменений
| Поле | Тип | Описание |
|---|---|---|
| order_id | FK→order | |
| user_id | FK→user | кто изменил |
| changed_at | datetime | когда |
| field / field_label | varchar | какое поле |
| old_value / new_value | text | старое / новое значение |

### files_orderfile — Файл заказа
| Поле | Тип | Описание |
|---|---|---|
| order_id | FK→order | |
| order_number | int | номер заказа |
| original_name | varchar | исходное имя файла |
| stored_name | varchar | имя на диске (с «_» при откреплении) |
| rel_path | varchar | путь относительно ORDER_FILES_ROOT |
| size | bigint | размер |
| content_type | varchar | MIME-тип |
| uploaded_at | datetime | дата загрузки |
| uploaded_by_id | FK→user | кто загрузил |
| is_detached | bool | откреплён от карточки |
| detached_at | datetime | когда откреплён |

### backups_backup — Резервная копия
| Поле | Тип | Описание |
|---|---|---|
| filename / rel_path | varchar | имя/путь файла копии |
| size | bigint | размер |
| kind | varchar | `auto` / `manual` |
| status | varchar | `ok` / `failed` |
| note | varchar | примечание/ошибка |
| created_at | datetime | дата создания |
| created_by_id | FK→user | кто создал (для ручных) |

### audit_actionlog — Журнал действий
| Поле | Тип | Описание |
|---|---|---|
| user_id | FK→user | кто |
| action_type | varchar | тип действия |
| summary | varchar | описание |
| target_type / target_id | varchar | объект |
| ip_address | inet | IP |
| created_at | datetime | время (UTC) |

## Soft delete

Физическое удаление заказов и файлов запрещено. Заказ можно только перевести в
статус «Отмена» (или закрыть «Произведён»). Файл при удалении из карточки
переименовывается («_»), но остаётся на диске.

## Миграции

Схема управляется миграциями Django (`app/apps/*/migrations`). Применяются
автоматически при старте контейнера `web` либо вручную:

```bash
docker compose exec web python manage.py migrate
```
