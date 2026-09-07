import app_animation.transitions
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0008_animation_song_slide_display_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="animation",
            name="default_transition",
            field=models.CharField(
                default=app_animation.transitions.get_default_transition_id,
                max_length=64,
            ),
        ),
    ]
