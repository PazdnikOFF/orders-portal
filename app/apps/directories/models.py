"""Reference data: organizations (TЗ §15, amendments §7–§8).

The employee directory was merged into accounts.User — a role=MANAGER user is
assigned to orders as «Менеджер».
"""
from django.db import models
from django.utils import timezone


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

    @property
    def rusprofile_url(self) -> str:
        """Link to the company card on Rusprofile (search by INN)."""
        return f"https://www.rusprofile.ru/search?query={self.inn}"
