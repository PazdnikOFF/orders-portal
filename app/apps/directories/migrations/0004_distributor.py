"""Add the Distributor directory (separate admin-managed entity)."""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("directories", "0003_delete_employee"),
    ]

    operations = [
        migrations.CreateModel(
            name="Distributor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inn", models.CharField(db_index=True, max_length=12, unique=True, verbose_name="ИНН")),
                ("name", models.CharField(blank=True, max_length=500, verbose_name="Наименование")),
                ("full_name", models.CharField(blank=True, max_length=1000, verbose_name="Полное наименование")),
                ("kpp", models.CharField(blank=True, max_length=9, verbose_name="КПП")),
                ("ogrn", models.CharField(blank=True, max_length=15, verbose_name="ОГРН")),
                ("address", models.CharField(blank=True, max_length=1000, verbose_name="Юридический адрес")),
                ("status", models.CharField(blank=True, max_length=50, verbose_name="Статус организации")),
                ("source", models.CharField(blank=True, max_length=50, verbose_name="Источник данных")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="Дата последнего обновления")),
            ],
            options={
                "verbose_name": "Дистрибьютор",
                "verbose_name_plural": "Дистрибьюторы",
                "ordering": ["name", "inn"],
            },
        ),
    ]
