"""
Seed initial managers from the Bitrix24 «Сотрудник» list.

Run on the server:

    docker compose exec web python manage.py seed_managers

Re-running is safe: existing users are matched by username and
last_name+first_name; their full name, role and password are refreshed.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User

# (last_name, first_name, username) — usernames are stable English IDs.
MANAGERS = [
    ("Ботнор",      "Полина",     "botnor"),
    ("Бушуева",     "Гульнара",   "bushueva"),
    ("Дмитриев",    "Алексей",    "dmitriev"),
    ("Кутаков",     "Алексей",    "kutakov"),
    ("Ланцова",     "Светлана",   "lantsova"),
    ("Лумпов",      "Максим",     "lumpov"),
    ("Мухнуров",    "Айваз",      "mukhnurov"),
    ("Павлова",     "Дарья",      "pavlova"),
    ("Плавинская",  "Юлия",       "plavinskaya"),
    ("Плахтиенко",  "Дарья",      "plakhtienko"),
    ("Санатина",    "Юлия",       "sanatina"),
    ("Смольков",    "Александр",  "smolkov"),
]

DEFAULT_PASSWORD = "132456"


class Command(BaseCommand):
    help = "Создаёт/обновляет пользователей-менеджеров с паролем по умолчанию."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", default=DEFAULT_PASSWORD,
            help=f"Пароль для всех создаваемых менеджеров (по умолчанию {DEFAULT_PASSWORD!r}).",
        )
        parser.add_argument(
            "--no-reset-password", action="store_true",
            help="Не сбрасывать пароль у уже существующих пользователей.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        password = opts["password"]
        reset_pwd = not opts["no_reset_password"]

        created, updated = 0, 0
        for last, first, username in MANAGERS:
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "last_name": last,
                    "first_name": first,
                    "role": Role.MANAGER,
                    "is_active": True,
                },
            )
            if was_created:
                user.set_password(password)
                user.save()
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"+ создан {user.username:>14}  {last} {first}"
                ))
                continue

            changed = []
            if user.last_name != last:
                user.last_name = last
                changed.append("фамилия")
            if user.first_name != first:
                user.first_name = first
                changed.append("имя")
            if user.role != Role.MANAGER:
                user.role = Role.MANAGER
                changed.append("роль")
            if not user.is_active:
                user.is_active = True
                changed.append("активен")
            if reset_pwd:
                user.set_password(password)
                changed.append("пароль")
            if changed:
                user.save()
                updated += 1
                self.stdout.write(self.style.WARNING(
                    f"~ обновлён {user.username:>14}  {last} {first}  ({', '.join(changed)})"
                ))
            else:
                self.stdout.write(
                    f"= без изменений {user.username:>14}  {last} {first}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Готово: создано {created}, обновлено {updated}, всего в списке {len(MANAGERS)}."
        ))
        self.stdout.write(self.style.WARNING(
            f"Пароль для входа: {password!r} — попросите менеджеров сменить его после первого входа."
        ))
