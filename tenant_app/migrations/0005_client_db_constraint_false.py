import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Drop cross-schema FK constraints added by 0004 on already-migrated DBs."""

    dependencies = [
        ("tenant_app", "0004_member_region_client"),
    ]

    operations = [
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
    ]
