from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0003_replace_song_favorites_table"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'UPDATE "lss"."s_song_links" '
                "SET type = 'audio' "
                "WHERE type = 'audio-video'"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="songlink",
            name="type",
            field=models.CharField(
                choices=[
                    ("score", "partition"),
                    ("audio", "audio"),
                    ("youtube", "YouTube"),
                    ("web", "page Web"),
                    ("internal", "lien interne - Lyrics Slide Show"),
                ],
                default="score",
                max_length=20,
            ),
        ),
    ]
