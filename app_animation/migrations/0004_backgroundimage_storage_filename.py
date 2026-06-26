from pathlib import PurePosixPath

from django.db import migrations, models


def populate_storage_filename(apps, schema_editor):
    BackgroundImage = apps.get_model("app_animation", "BackgroundImage")
    for image in BackgroundImage.objects.all().only("image_id", "stored_path"):
        filename = PurePosixPath(str(image.stored_path or "")).name.strip()
        if not filename:
            raise RuntimeError(
                f"BackgroundImage {image.image_id} has no filename in stored_path."
            )
        image.storage_filename = filename
        image.save(update_fields=["storage_filename"])


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0003_background_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="backgroundimage",
            name="storage_filename",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.RunPython(
            populate_storage_filename,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="backgroundimage",
            name="storage_filename",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
