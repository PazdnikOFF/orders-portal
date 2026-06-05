"""Action log — who did what, when (TЗ §18)."""
from django.conf import settings
from django.db import models


class ActionType(models.TextChoices):
    LOGIN = "login", "Вход"
    LOGOUT = "logout", "Выход"
    USER_CREATE = "user_create", "Создание пользователя"
    USER_UPDATE = "user_update", "Изменение пользователя"
    USER_BLOCK = "user_block", "Блокировка пользователя"
    USER_UNBLOCK = "user_unblock", "Разблокировка пользователя"
    ORDER_CREATE = "order_create", "Создание заказа"
    ORDER_UPDATE = "order_update", "Изменение заказа"
    STATUS_CHANGE = "status_change", "Изменение статуса"
    FILE_UPLOAD = "file_upload", "Загрузка файла"
    FILE_DETACH = "file_detach", "Удаление файла из карточки"
    BACKUP_CREATE = "backup_create", "Создание резервной копии"
    BACKUP_RESTORE = "backup_restore", "Восстановление из копии"
    BACKUP_DELETE = "backup_delete", "Удаление резервной копии"


class ActionLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="actions", verbose_name="Пользователь",
    )
    action_type = models.CharField("Действие", max_length=32, choices=ActionType.choices)
    summary = models.CharField("Описание", max_length=500, blank=True)
    target_type = models.CharField("Тип объекта", max_length=64, blank=True)
    target_id = models.CharField("ID объекта", max_length=64, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("Время (UTC)", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал действий"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.get_action_type_display()}"
