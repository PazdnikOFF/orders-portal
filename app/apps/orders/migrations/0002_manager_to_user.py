"""Repoint Order.manager from directories.Employee to accounts.User.

For every employee currently assigned as a manager we create (once) a matching
User with role=MANAGER, then move the FK over. Existing orders keep their
manager. The auto-created users get an unusable password — an admin sets one
later via the user form.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def remap_managers(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    User = apps.get_model("accounts", "User")
    Employee = apps.get_model("directories", "Employee")
    from django.utils import timezone

    emp_to_user = {}
    for order in Order.objects.all():
        emp_id = order.manager_id
        if emp_id not in emp_to_user:
            emp = Employee.objects.get(pk=emp_id)
            base = "emp%s" % emp.pk
            username = base
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = "%s_%s" % (base, suffix)
                suffix += 1
            user = User.objects.create(
                username=username,
                last_name=emp.last_name or "",
                first_name=emp.first_name or "",
                middle_name=getattr(emp, "middle_name", "") or "",
                role="manager",
                is_active=emp.is_active,
                is_staff=False,
                is_superuser=False,
                password="!merged-no-login",
                date_joined=timezone.now(),
            )
            emp_to_user[emp_id] = user.pk
        order.manager_user_id = emp_to_user[emp_id]
        order.save(update_fields=["manager_user"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        ("accounts", "0002_merge_employee"),
        ("directories", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="manager_user",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL, related_name="managed_orders",
                verbose_name="Менеджер",
            ),
        ),
        migrations.RunPython(remap_managers, migrations.RunPython.noop),
        migrations.RemoveField(model_name="order", name="manager"),
        migrations.RenameField(model_name="order", old_name="manager_user", new_name="manager"),
        migrations.AlterField(
            model_name="order",
            name="manager",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL, related_name="managed_orders",
                verbose_name="Менеджер",
            ),
        ),
    ]
