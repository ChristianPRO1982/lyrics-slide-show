from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0011_animation_remote_master_transport"),
    ]

    operations = [
        migrations.AddField(
            model_name="animationremotesession",
            name="remote_connection_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
