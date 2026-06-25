from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0004_song_link_types_are_distinct"),
    ]

    operations = [
        migrations.AddField(
            model_name="songmessage",
            name="is_read",
            field=models.BooleanField(db_column="vu", default=False),
        ),
        migrations.RunSQL(
            sql=(
                'UPDATE "lss"."s_song_messages" '
                'SET "vu" = CASE WHEN "status" = 0 THEN FALSE ELSE TRUE END'
            ),
            reverse_sql=(
                'UPDATE "lss"."s_song_messages" '
                'SET "status" = CASE WHEN "vu" THEN 1 ELSE 0 END'
            ),
        ),
        migrations.RemoveField(
            model_name="songmessage",
            name="status",
        ),
    ]
