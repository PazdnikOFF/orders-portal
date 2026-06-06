"""Remove the Employee model — merged into accounts.User."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("directories", "0002_alter_organization_inn_organization_uniq_org_inn_kpp"),
        ("orders", "0002_manager_to_user"),
        ("accounts", "0002_merge_employee"),
    ]

    operations = [
        migrations.DeleteModel(name="Employee"),
    ]
