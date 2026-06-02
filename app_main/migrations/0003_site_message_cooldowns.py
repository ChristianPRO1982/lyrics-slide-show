# Generated manually for site popup cooldown support.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_main", "0002_directoryuserrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteparams",
            name="admin_message_cooldown_minutes",
            field=models.IntegerField(default=5),
        ),
        migrations.AddField(
            model_name="siteparams",
            name="moderator_message_cooldown_minutes",
            field=models.IntegerField(default=60),
        ),
    ]
