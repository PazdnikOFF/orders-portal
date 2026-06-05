"""Order file metadata (TЗ §6/§15.5). Files live on disk; deletion is soft."""
from django.conf import settings
from django.db import models
from django.urls import reverse


class OrderFile(models.Model):
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="files", verbose_name="Заказ"
    )
    order_number = models.PositiveIntegerField("Номер заказа", db_index=True)
    original_name = models.CharField("Исходное имя файла", max_length=255)
    stored_name = models.CharField("Имя файла на диске", max_length=255)
    # Path relative to settings.ORDER_FILES_ROOT, e.g. "1/ORD-000001.pdf".
    rel_path = models.CharField("Путь к файлу", max_length=500)
    size = models.PositiveBigIntegerField("Размер файла", default=0)
    content_type = models.CharField("MIME-тип", max_length=120, blank=True)
    uploaded_at = models.DateTimeField("Дата загрузки", auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="uploaded_files", verbose_name="Загрузил",
    )
    # «Признак удаления из карточки» — link removed, file kept on disk (renamed).
    is_detached = models.BooleanField("Удалён из карточки", default=False)
    detached_at = models.DateTimeField("Дата удаления из карточки", null=True, blank=True)

    class Meta:
        verbose_name = "Файл заказа"
        verbose_name_plural = "Файлы заказов"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.stored_name

    @property
    def abs_path(self):
        return settings.ORDER_FILES_ROOT / self.rel_path

    @property
    def serve_url(self) -> str:
        return reverse("files:serve", args=[self.pk])

    @property
    def internal_redirect(self) -> str:
        """X-Accel-Redirect target for protected nginx delivery (TЗ §17)."""
        return settings.ORDER_FILES_INTERNAL_PREFIX + self.rel_path
