from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0005_create_common_targets"),
    ]

    operations = [
        migrations.AlterField(
            model_name="backgroundimage",
            name="target",
            field=models.CharField(max_length=255),
        ),
    ]
