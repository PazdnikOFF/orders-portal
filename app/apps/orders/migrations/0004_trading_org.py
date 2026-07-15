import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("directories", "0004_distributor"),
        ("orders", "0003_distributor_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="trading_org",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="trading_org_orders",
                to="directories.organization",
                verbose_name="Торгующая организация",
            ),
        ),
    ]
