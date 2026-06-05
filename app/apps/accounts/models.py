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

    full_name = models.CharField("ФИО", max_length=255, blank=True)
    role = models.CharField(
        "Роль", max_length=16, choices=Role.choices, default=Role.OPERATOR
    )
    # Links a Manager/Operator user to their entry in the employee directory.
    # Used so a Manager sees only orders where he is the assigned «Менеджер».
    employee = models.ForeignKey(
        "directories.Employee", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="user_accounts", verbose_name="Сотрудник (профиль)",
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["full_name", "username"]

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
    def display_name(self) -> str:
        return self.full_name or self.get_full_name() or self.username

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
