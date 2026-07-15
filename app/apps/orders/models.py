"""Order model, gapless numbering, and change history (TЗ §10/§15, amendments §9/§10)."""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from . import matrix


class Status(models.TextChoices):
    PLANNED = "planned", "В плане"
    IN_PROGRESS = "in_progress", "В работе"
    PRODUCED = "produced", "Произведен"
    CANCELLED = "cancelled", "Отмена"


# status value -> matrix stage key
STATUS_TO_STAGE = {
    Status.PLANNED: matrix.STAGE_PLANNED,
    Status.IN_PROGRESS: matrix.STAGE_IN_PROGRESS,
    Status.PRODUCED: matrix.STAGE_PRODUCED,
    Status.CANCELLED: matrix.STAGE_CANCELLED,
}

# Kanban columns (amendment §4) and which targets are reachable from each status.
KANBAN_STATUSES = [Status.PLANNED, Status.IN_PROGRESS, Status.PRODUCED, Status.CANCELLED]


class OrderSequence(models.Model):
    """
    Gapless order-number allocator (amendment §9: «пропуск номеров запрещён»).

    A plain PostgreSQL sequence guarantees uniqueness but NOT gaplessness (it
    advances on rollback). We instead increment a row under SELECT ... FOR
    UPDATE inside the same transaction as order creation, so a rollback also
    rolls back the number — strictly sequential, no gaps, no reuse.
    """

    name = models.CharField(max_length=50, unique=True, default="order_number")
    value = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "Счётчик номеров"
        verbose_name_plural = "Счётчики номеров"

    @classmethod
    def next_value(cls, name: str = "order_number") -> int:
        seq = cls.objects.select_for_update().filter(name=name).first()
        if seq is None:
            seq = cls.objects.create(name=name, value=0)
            seq = cls.objects.select_for_update().get(pk=seq.pk)
        seq.value += 1
        seq.save(update_fields=["value"])
        return seq.value


class Order(models.Model):
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="managed_orders", verbose_name="Менеджер",
    )
    distributor = models.ForeignKey(
        "directories.Distributor", on_delete=models.PROTECT,
        related_name="orders", verbose_name="Дистрибьютор",
    )
    # «Торгующая организация» — необязательное поле, выбирается по ИНН через
    # DaData (как «Потенциальный пользователь»), заполняется при создании.
    trading_org = models.ForeignKey(
        "directories.Organization", on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="trading_org_orders", verbose_name="Торгующая организация",
    )
    potential_user = models.ForeignKey(
        "directories.Organization", on_delete=models.PROTECT,
        related_name="potential_user_orders", verbose_name="Потенциальный пользователь",
    )
    # «Комментарий / Участники проекта» — dynamic list of organizations (amendment §7).
    participants = models.ManyToManyField(
        "directories.Organization", blank=True,
        related_name="participant_orders", verbose_name="Участники проекта",
    )
    kit = models.CharField("Комплект", max_length=500)
    request_date = models.DateField("Дата обращения", default=timezone.localdate, editable=False)
    forecast_date = models.DateField("Прогнозируемая дата реализации")
    order_number = models.PositiveIntegerField("Номер заказа", unique=True, editable=False)
    status = models.CharField(
        "Статус", max_length=16, choices=Status.choices, default=Status.PLANNED, db_index=True,
    )

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата изменения", auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_orders", verbose_name="Создал",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="updated_orders", verbose_name="Изменил",
    )

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-order_number"]

    def __str__(self):
        return f"Заказ №{self.order_number}"

    @property
    def stage(self) -> str:
        return STATUS_TO_STAGE.get(self.status, matrix.STAGE_PLANNED)

    @property
    def is_locked(self) -> bool:
        """Produced/Cancelled lock all fields for non-admins (TЗ §12.9)."""
        return self.status in (Status.PRODUCED, Status.CANCELLED)

    @property
    def order_code(self) -> str:
        """Human-readable order number, e.g. РЭ-000001."""
        return f"РЭ-{self.order_number:06d}"

    @property
    def file_code(self) -> str:
        """ASCII form used for on-disk file names (avoids Cyrillic filenames)."""
        return f"RE-{self.order_number:06d}"

    @staticmethod
    def org_display_list(orgs):
        """
        Build display strings for a set of organizations. If the same INN occurs
        more than once (different КПП — branches), the КПП is appended so the
        rows are distinguishable; otherwise «Наименование (ИНН)» (amendment §8).
        """
        orgs = list(orgs)
        inn_counts = {}
        for o in orgs:
            inn_counts[o.inn] = inn_counts.get(o.inn, 0) + 1
        result = []
        for o in orgs:
            label = o.name or o.full_name or "—"
            if inn_counts[o.inn] > 1 and o.kpp:
                text = f"{label} ({o.inn}, КПП {o.kpp})"
            else:
                text = f"{label} ({o.inn})"
            result.append({"org": o, "display": text})
        return result

    def participants_display(self):
        return self.org_display_list(self.participants.all())

    @property
    def forecast_urgency(self) -> str:
        """
        Deadline proximity for the forecast date (TЗ UX):
          "due-soon"  — less than 2 weeks left (orange, includes overdue),
          "due-month" — less than a month left (blue),
          ""          — far enough / closed order.
        """
        if self.status in (Status.PRODUCED, Status.CANCELLED) or not self.forecast_date:
            return ""
        delta = (self.forecast_date - timezone.localdate()).days
        if delta < 14:
            return "due-soon"
        if delta < 30:
            return "due-month"
        return ""

    @property
    def active_file(self):
        """The currently attached (non-detached) order file, if any."""
        return self.files.filter(is_detached=False).order_by("-uploaded_at").first()

    def save(self, *args, **kwargs):
        if self._state.adding and not self.order_number:
            with transaction.atomic():
                self.order_number = OrderSequence.next_value()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class OrderHistory(models.Model):
    """Per-field change history (amendment §10 — кто/когда/поле/старое/новое)."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="history", verbose_name="Заказ"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, verbose_name="Кто изменил"
    )
    changed_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)
    field = models.CharField("Поле", max_length=64)
    field_label = models.CharField("Название поля", max_length=128, blank=True)
    old_value = models.TextField("Старое значение", blank=True)
    new_value = models.TextField("Новое значение", blank=True)

    class Meta:
        verbose_name = "Изменение заказа"
        verbose_name_plural = "История изменений"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.order} · {self.field}"
