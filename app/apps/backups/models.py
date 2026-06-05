"""Backup catalog (TЗ §5). Records each dump; admin module manages them."""
from django.conf import settings
from django.db import models


class BackupKind(models.TextChoices):
    AUTO = "auto", "Автоматически"
    MANUAL = "manual", "Вручную"


class BackupStatus(models.TextChoices):
    OK = "ok", "Готова"
    FAILED = "failed", "Ошибка"


class Backup(models.Model):
    filename = models.CharField("Имя файла", max_length=255)
    rel_path = models.CharField("Путь", max_length=500)
    size = models.PositiveBigIntegerField("Размер", default=0)
    kind = models.CharField("Тип", max_length=10, choices=BackupKind.choices, default=BackupKind.AUTO)
    status = models.CharField("Статус", max_length=10, choices=BackupStatus.choices, default=BackupStatus.OK)
    note = models.CharField("Примечание", max_length=500, blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="backups", verbose_name="Создал",
    )

    class Meta:
        verbose_name = "Резервная копия"
        verbose_name_plural = "Резервные копии"
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename

    @property
    def abs_path(self):
        return settings.BACKUP_ROOT / self.rel_path

    @property
    def exists_on_disk(self) -> bool:
        return self.abs_path.exists()
