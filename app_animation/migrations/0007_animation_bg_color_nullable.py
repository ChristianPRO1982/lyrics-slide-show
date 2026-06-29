# Generated manually for nullable animation background colors.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0006_expand_background_target_length"),
    ]

    operations = [
        migrations.AlterField(
            model_name="animation",
            name="bg_color",
            field=models.CharField(
                blank=True,
                default="#000000",
                max_length=32,
                null=True,
            ),
        ),
    ]
