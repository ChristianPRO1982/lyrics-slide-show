import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0009_animation_default_transition"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnimationRemoteSession",
            fields=[
                (
                    "session_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("access_token_digest", models.CharField(max_length=64, unique=True)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("last_remote_command_at", models.DateTimeField(blank=True, null=True)),
                ("master_connected_at", models.DateTimeField(blank=True, null=True)),
                ("latest_state", models.JSONField(default=dict)),
                ("latest_state_revision", models.IntegerField(default=-1)),
                (
                    "animation",
                    models.ForeignKey(
                        db_column="animation_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remote_sessions",
                        to="app_animation.animation",
                    ),
                ),
            ],
            options={
                "db_table": 'lss"."a_animation_remote_sessions',
            },
        ),
        migrations.AddIndex(
            model_name="animationremotesession",
            index=models.Index(
                fields=["active", "expires_at"],
                name="a_anim_remote_active_exp_idx",
            ),
        ),
    ]
