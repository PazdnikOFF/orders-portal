"""
Fix the typo: «Ботнер» → «Ботнор» (and login botner → botnor).

Idempotent: re-running does nothing if everything is already correct.
Updates both the User record and any audit log entries that mention the
old spelling.

Usage on the server:

    docker compose exec web python manage.py fix_botnor
    docker compose exec web python manage.py fix_botnor --dry-run    # без записи
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User


REPLACES = [
    ("botner", "botnor"),  # username
    ("Ботнер", "Ботнор"),  # фамилия / упоминания в журнале
]


class Command(BaseCommand):
    help = "Заменяет логин «botner» на «botnor» и фамилию «Ботнер» на «Ботнор»."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Только показать, что будет изменено, без записи.")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        actions = []

        # --- 1) пользователь ---
        # ищем и по «битому» логину, и по правильному (на случай если уже
        # поменян, но фамилия осталась со старой опечаткой)
        user = (User.objects.filter(username__iexact="botner").first()
                or User.objects.filter(username__iexact="botnor").first()
                or User.objects.filter(last_name="Ботнер").first())
        if user is None:
            self.stdout.write(self.style.WARNING(
                "Пользователя с логином botner/botnor или фамилией «Ботнер» не нашёл."
            ))
            return

        if user.username != "botnor":
            actions.append(f"username: {user.username!r} → 'botnor'")
            if not dry:
                user.username = "botnor"
        if user.last_name != "Ботнор":
            actions.append(f"last_name: {user.last_name!r} → 'Ботнор'")
            if not dry:
                user.last_name = "Ботнор"
        if not dry and actions:
            user.save(update_fields=["username", "last_name"])

        # --- 2) журнал действий — поправим текстовые упоминания ---
        try:
            from apps.audit.models import ActionLog
        except ImportError:
            ActionLog = None

        log_changes = 0
        if ActionLog is not None:
            for old, new in REPLACES:
                qs = ActionLog.objects.filter(summary__contains=old)
                if dry:
                    log_changes += qs.count()
                else:
                    for entry in qs:
                        entry.summary = entry.summary.replace(old, new)
                        entry.save(update_fields=["summary"])
                        log_changes += 1

        # --- 3) отчёт ---
        if not actions and log_changes == 0:
            self.stdout.write(self.style.SUCCESS("Ничего менять не нужно — уже правильно."))
            return

        self.stdout.write(self.style.SUCCESS("Готово." if not dry else "Будет сделано (dry-run):"))
        for a in actions:
            self.stdout.write("  • " + a)
        if log_changes:
            self.stdout.write(f"  • журнал действий: {'будет обновлено' if dry else 'обновлено'} {log_changes} записей")
        if dry:
            self.stdout.write(self.style.WARNING("Запусти без --dry-run, чтобы применить."))
