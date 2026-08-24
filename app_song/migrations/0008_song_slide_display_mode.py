# Generated manually to add song slide display mode.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_song", "0007_update_search_song_catalog_text_pattern"),
    ]

    operations = [
        migrations.AddField(
            model_name="song",
            name="slide_display_mode",
            field=models.CharField(
                choices=[
                    ("single", "Single slide"),
                    (
                        "chorus_then_parallel",
                        "Chorus alone, then chorus with verse",
                    ),
                    (
                        "chorus_always_parallel",
                        "Chorus and verse always in parallel",
                    ),
                    ("verses_by_pairs", "Verses by pairs"),
                ],
                default="single",
                max_length=32,
            ),
        ),
    ]
