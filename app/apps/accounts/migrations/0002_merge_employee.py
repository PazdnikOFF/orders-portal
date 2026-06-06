"""Merge the Employee directory into User: add ФИО fields, drop full_name/employee."""
from django.db import migrations, models


def copy_full_name(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        if not user.last_name and getattr(user, "full_name", ""):
            user.last_name = user.full_name[:150]
            user.save(update_fields=["last_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="middle_name",
            field=models.CharField("Отчество", max_length=150, blank=True),
        ),
        migrations.RunPython(copy_full_name, migrations.RunPython.noop),
        migrations.RemoveField(model_name="user", name="full_name"),
        migrations.RemoveField(model_name="user", name="employee"),
        migrations.AlterModelOptions(
            name="user",
            options={
                "ordering": ["last_name", "first_name", "username"],
                "verbose_name": "Пользователь",
                "verbose_name_plural": "Пользователи",
            },
        ),
    ]
