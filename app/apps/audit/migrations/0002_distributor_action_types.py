"""Add distributor action types to ActionLog.action_type choices."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="actionlog",
            name="action_type",
            field=models.CharField(
                choices=[
                    ("login", "Вход"),
                    ("logout", "Выход"),
                    ("user_create", "Создание пользователя"),
                    ("user_update", "Изменение пользователя"),
                    ("user_block", "Блокировка пользователя"),
                    ("user_unblock", "Разблокировка пользователя"),
                    ("order_create", "Создание заказа"),
                    ("order_update", "Изменение заказа"),
                    ("status_change", "Изменение статуса"),
                    ("file_upload", "Загрузка файла"),
                    ("file_detach", "Удаление файла из карточки"),
                    ("backup_create", "Создание резервной копии"),
                    ("backup_restore", "Восстановление из копии"),
                    ("backup_delete", "Удаление резервной копии"),
                    ("distributor_create", "Добавление дистрибьютора"),
                    ("distributor_update", "Изменение дистрибьютора"),
                    ("distributor_toggle", "Вкл/выкл дистрибьютора"),
                ],
                max_length=32,
                verbose_name="Действие",
            ),
        ),
    ]
