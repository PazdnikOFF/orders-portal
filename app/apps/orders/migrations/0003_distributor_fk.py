"""
Repoint Order.distributor from directories.Organization to the new
directories.Distributor, migrating existing data.

Existing orders reference an Organization as their distributor. For each
distinct INN we create (once) a Distributor with the same details, then point
the order at it. Organizations are left untouched (they're still used for the
potential user and the «Комментарий» participants).

Forward-only: the data step has a noop reverse — we don't reconstruct the old
Organization FK on downgrade (production never reverses this).
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def forward(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Distributor = apps.get_model("directories", "Distributor")
    by_inn = {}
    for order in Order.objects.select_related("distributor").all():
        org = order.distributor
        if org is None:
            continue
        inn = (org.inn or "").strip()
        dist = by_inn.get(inn)
        if dist is None:
            dist, _ = Distributor.objects.get_or_create(
                inn=inn,
                defaults={
                    "name": org.name or org.full_name or "",
                    "full_name": org.full_name or "",
                    "kpp": org.kpp or "",
                    "ogrn": org.ogrn or "",
                    "address": org.address or "",
                    "status": org.status or "",
                    "source": org.source or "",
                    "is_active": True,
                    "updated_at": django.utils.timezone.now(),
                },
            )
            by_inn[inn] = dist
        order.distributor_ref_id = dist.pk
        order.save(update_fields=["distributor_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_manager_to_user"),
        ("directories", "0004_distributor"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="distributor_ref",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="directories.distributor",
                verbose_name="Дистрибьютор",
            ),
        ),
        migrations.RunPython(forward, migrations.RunPython.noop),
        migrations.RemoveField(model_name="order", name="distributor"),
        migrations.RenameField(
            model_name="order", old_name="distributor_ref", new_name="distributor"
        ),
        migrations.AlterField(
            model_name="order",
            name="distributor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="directories.distributor",
                verbose_name="Дистрибьютор",
            ),
        ),
    ]
