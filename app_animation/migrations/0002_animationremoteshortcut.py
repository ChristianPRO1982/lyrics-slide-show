# Generated manually for animation remote shortcut persistence.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnimationRemoteShortcut",
            fields=[
                (
                    "member_id",
                    models.UUIDField(editable=False, primary_key=True, serialize=False),
                ),
                ("lyrics_slide_show_bindings", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": 'lss"."m_animation_remote_shortcuts',
            },
        ),
    ]
