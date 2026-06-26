# Generated manually for background image library support.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0002_animationremoteshortcut"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackgroundImage",
            fields=[
                ("image_id", models.AutoField(primary_key=True, serialize=False)),
                ("asset_code", models.CharField(max_length=128, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("target", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("inactive", "Inactive"),
                            ("active", "Active"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("stored_path", models.CharField(max_length=255)),
                ("original_name", models.CharField(max_length=255)),
                ("extension", models.CharField(max_length=16)),
                ("mime", models.CharField(max_length=100)),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("width", models.PositiveIntegerField(default=0)),
                ("height", models.PositiveIntegerField(default=0)),
                ("member_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("moderated_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": 'lss"."a_background_images',
                "ordering": ["title", "image_id"],
            },
        ),
        migrations.AddIndex(
            model_name="backgroundimage",
            index=models.Index(fields=["status"], name="a_bg_images_status_idx"),
        ),
        migrations.AddIndex(
            model_name="backgroundimage",
            index=models.Index(fields=["asset_code"], name="a_bg_images_asset_idx"),
        ),
        migrations.CreateModel(
            name="BackgroundImageGenre",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("genre_id", models.IntegerField()),
                (
                    "image",
                    models.ForeignKey(
                        db_column="image_id",
                        on_delete=models.deletion.CASCADE,
                        related_name="genre_relations",
                        to="app_animation.backgroundimage",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."a_background_image_genres',
            },
        ),
        migrations.AddConstraint(
            model_name="backgroundimagegenre",
            constraint=models.UniqueConstraint(
                fields=("image", "genre_id"),
                name="a_bg_image_genres_unique",
            ),
        ),
    ]
