"""Reference data: employees and organizations (TЗ §15, amendments §5–§8)."""
from django.db import models
from django.utils import timezone


class EmployeeType(models.TextChoices):
    MANAGER = "manager", "Менеджер"
    OPERATOR = "operator", "Оператор"
    DIRECTOR = "director", "Руководитель"
    ADMIN = "admin", "Администратор"
    OTHER = "other", "Прочее"


class Employee(models.Model):
    """Справочник сотрудников. Отображается как «Фамилия Имя» (amendment §5)."""

    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    middle_name = models.CharField("Отчество", max_length=100, blank=True)
    type = models.CharField(
        "Тип сотрудника", max_length=16, choices=EmployeeType.choices,
        default=EmployeeType.OTHER, db_index=True,
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.short_name

    @property
    def short_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()


class Organization(models.Model):
    """
    Справочник организаций (Дистрибьютор / Потенциальный пользователь /
    Участники). Заполняется по ИНН через провайдера. Отображается как
    «Наименование (ИНН)» (amendment §8).
    """

    # An INN can have several КПП (head office + branches), so the natural key
    # is (inn, kpp) — that lets the user pick a specific branch from DaData.
    inn = models.CharField("ИНН", max_length=12, db_index=True)
    name = models.CharField("Наименование", max_length=500, blank=True)
    full_name = models.CharField("Полное наименование", max_length=1000, blank=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    ogrn = models.CharField("ОГРН", max_length=15, blank=True)
    address = models.CharField("Юридический адрес", max_length=1000, blank=True)
    status = models.CharField("Статус организации", max_length=50, blank=True)
    source = models.CharField("Источник данных", max_length=50, blank=True)
    updated_at = models.DateTimeField("Дата последнего обновления", default=timezone.now)

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"
        ordering = ["name", "inn"]
        constraints = [
            models.UniqueConstraint(fields=["inn", "kpp"], name="uniq_org_inn_kpp"),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self) -> str:
        """Form/table display — «Наименование (ИНН)» (amendment §8)."""
        label = self.name or self.full_name or "Без наименования"
        return f"{label} ({self.inn})"

    @property
    def option_label(self) -> str:
        """Dropdown label — name + КПП so branches are distinguishable."""
        label = self.name or self.full_name or self.inn
        return f"{label} · КПП {self.kpp}" if self.kpp else label
