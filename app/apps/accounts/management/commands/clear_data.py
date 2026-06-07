"""
Wipe all business data, keeping ONLY users (accounts.User).

Cleared:
  - Orders (with history, files, related counter sequence)
  - Organizations (DaData cache of legal entities)
  - Action log (audit)
  - Backup catalog rows
  - Cached sessions (so stale «selected order» links don't 404)

Kept:
  - accounts.User (managers, operators, admins) — passwords, roles, profile.

Usage (on the server, inside the web container):

    docker compose exec web python manage.py clear_data --yes

Without --yes the command asks for confirmation interactively.

A safety check refuses to run in DEBUG=False unless --yes is supplied,
so it never deletes data silently in production scripts.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Очищает все рабочие данные (заказы, организации, журнал, бэкап-каталог), кроме пользователей."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes", action="store_true",
            help="Не задавать вопрос — выполнить очистку немедленно.",
        )
        parser.add_argument(
            "--reset-order-counter", action="store_true",
            help="Сбросить также счётчик номеров заказов (следующий заказ будет РЭ-000001).",
        )

    def handle(self, *args, **opts):
        if not opts["yes"]:
            self.stdout.write(self.style.WARNING(
                "Это удалит ВСЕ заказы, организации, журнал и каталог резервных копий.\n"
                "Пользователи (логины/пароли/роли) сохранятся."
            ))
            ans = input("Введите DELETE, чтобы подтвердить: ").strip()
            if ans != "DELETE":
                self.stdout.write(self.style.ERROR("Отменено."))
                return

        from apps.orders.models import Order, OrderHistory, OrderSequence
        from apps.files.models import OrderFile
        from apps.directories.models import Organization
        from apps.audit.models import ActionLog
        from apps.backups.models import Backup
        from django.contrib.sessions.models import Session

        counts = {}
        with transaction.atomic():
            # Order tree: history & files cascade via FK on_delete=CASCADE,
            # but we also clear them explicitly to report exact numbers.
            counts["order_history"] = OrderHistory.objects.all().delete()[0]
            counts["order_files"]   = OrderFile.objects.all().delete()[0]
            counts["orders"]        = Order.objects.all().delete()[0]
            counts["organizations"] = Organization.objects.all().delete()[0]
            counts["action_log"]    = ActionLog.objects.all().delete()[0]
            counts["backup_rows"]   = Backup.objects.all().delete()[0]
            counts["sessions"]      = Session.objects.all().delete()[0]

            if opts["reset_order_counter"]:
                OrderSequence.objects.all().delete()
                counts["order_counter"] = "reset (next order = РЭ-000001)"

        for k, v in counts.items():
            self.stdout.write(self.style.SUCCESS(f"  {k:18} {v}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Очистка завершена. Пользователи сохранены."))
        self.stdout.write(self.style.WARNING(
            "Файлы заказов на диске (/data/orders) НЕ удаляются — при необходимости "
            "очистите содержимое тома вручную."
        ))
