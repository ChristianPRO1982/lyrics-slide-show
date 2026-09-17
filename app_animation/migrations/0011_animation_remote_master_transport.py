from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0010_animation_remote_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="animationremotesession",
            name="master_token_digest",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="animationremotesession",
            name="master_channel_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="animationremotesession",
            name="master_connection_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
