from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS unaccent;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
