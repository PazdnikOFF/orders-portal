"""Create the initial administrator on first deploy (idempotent)."""
import os

from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User


class Command(BaseCommand):
    help = "Создаёт первичного администратора из переменных окружения, если его ещё нет."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "")
        full_name = os.environ.get("ADMIN_FULL_NAME", "Администратор")

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.NOTICE(f"Пользователь «{username}» уже существует — пропуск."))
            return
        if not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_PASSWORD не задан — первичный администратор не создан. "
                "Задайте ADMIN_PASSWORD и перезапустите, либо создайте пользователя вручную."
            ))
            return

        user = User.objects.create_user(
            username=username, password=password, full_name=full_name, role=Role.ADMIN,
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Создан администратор «{user.username}»."))
