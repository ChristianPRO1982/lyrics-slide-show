from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0004_backgroundimage_storage_filename"),
    ]

    operations = [
        # `common.targets` belongs to the shared `common` schema and must be
        # provisioned outside LSS-owned Django migrations.
        migrations.RunSQL(
            sql=migrations.RunSQL.noop, reverse_sql=migrations.RunSQL.noop
        ),
    ]
