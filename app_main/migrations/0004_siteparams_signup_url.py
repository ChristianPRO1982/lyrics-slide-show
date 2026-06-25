from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_main", "0003_site_message_cooldowns"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteparams",
            name="signup_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
