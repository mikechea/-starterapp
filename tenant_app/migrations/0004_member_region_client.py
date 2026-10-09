import django.db.models.deletion
import django_multitenant.fields
from django.db import connection, migrations, models
from django_tenants.utils import get_public_schema_name, schema_context


def populate_client(apps, schema_editor):
    schema_name = connection.schema_name
    if schema_name == get_public_schema_name():
        return

    Client = apps.get_model("shared_app", "Client")
    Region = apps.get_model("tenant_app", "Region")
    Member = apps.get_model("tenant_app", "Member")

    with schema_context(get_public_schema_name()):
        client = Client.objects.get(schema_name=schema_name)

    Region.objects.filter(client_id__isnull=True).update(client_id=client.id)
    Member.objects.filter(client_id__isnull=True).update(client_id=client.id)


class Migration(migrations.Migration):

    dependencies = [
        ("shared_app", "0001_initial"),
        ("tenant_app", "0003_member_region"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="members",
                to="shared_app.client",
            ),
        ),
        migrations.AddField(
            model_name="region",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="regions",
                to="shared_app.client",
            ),
        ),
        migrations.RunPython(populate_client, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="member",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="members",
                to="shared_app.client",
            ),
        ),
        migrations.AlterField(
            model_name="region",
            name="client",
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="regions",
                to="shared_app.client",
            ),
        ),
        migrations.AlterField(
            model_name="member",
            name="region",
            field=django_multitenant.fields.TenantForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="members",
                to="tenant_app.region",
            ),
        ),
    ]
