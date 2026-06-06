"""User model with the four-role access model (TЗ §2.2, amendments §2)."""
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "admin", "Админ"
    OPERATOR = "operator", "Оператор"
    MANAGER = "manager", "Менеджер"
    DIRECTOR = "director", "Руководитель"


class UserManager(DjangoUserManager):
    """Keeps superusers in sync with the ADMIN role."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Portal user. `username` is the login; `is_active=False` means "заблокирован".
    The role drives every server-side permission check.
    """

    # The user IS the employee (merged entity): name + role live here, and a
    # role=MANAGER user is what gets assigned to orders as «Менеджер».
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    role = models.CharField(
        "Роль", max_length=16, choices=Role.choices, default=Role.OPERATOR
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        # ADMIN role implies Django staff/superuser so the admin site is reachable.
        if self.role == Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        else:
            self.is_superuser = False
        super().save(*args, **kwargs)

    @property
    def short_name(self) -> str:
        """«Фамилия Имя» — display used in lists and the manager dropdown."""
        return f"{self.last_name} {self.first_name}".strip() or self.username

    @property
    def display_name(self) -> str:
        return self.short_name

    @property
    def fio(self) -> str:
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip() or self.username

    # --- Role predicates ---------------------------------------------------- #
    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_operator(self) -> bool:
        return self.role == Role.OPERATOR

    @property
    def is_manager(self) -> bool:
        return self.role == Role.MANAGER

    @property
    def is_director(self) -> bool:
        return self.role == Role.DIRECTOR

    # --- Capability helpers (used by views, templates, API) ----------------- #
    @property
    def can_manage_users(self) -> bool:
        return self.is_admin

    @property
    def can_access_backups(self) -> bool:
        return self.is_admin

    @property
    def can_create_orders(self) -> bool:
        # Only Admin and Operator may create records (TЗ §3, amendment §2).
        return self.is_admin or self.is_operator

    @property
    def can_change_status(self) -> bool:
        return self.is_admin or self.is_operator

    @property
    def can_manage_files(self) -> bool:
        return self.is_admin or self.is_operator

    @property
    def sees_only_own_orders(self) -> bool:
        # Manager sees only records where he is the assigned manager.
        return self.is_manager
