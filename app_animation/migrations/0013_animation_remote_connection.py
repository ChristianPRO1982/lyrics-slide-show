import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0012_animation_remote_connection_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnimationRemoteConnection",
            fields=[
                (
                    "connection_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[("master", "Master"), ("remote", "Remote")],
                        max_length=16,
                    ),
                ),
                (
                    "channel_name",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("last_seen_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        db_column="session_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="connections",
                        to="app_animation.animationremotesession",
                    ),
                ),
            ],
            options={"db_table": 'lss"."a_animation_remote_connections'},
        ),
        migrations.AddIndex(
            model_name="animationremoteconnection",
            index=models.Index(
                fields=["session", "role"], name="a_anim_remote_conn_role_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="animationremoteconnection",
            index=models.Index(
                fields=["last_seen_at"], name="a_anim_remote_conn_seen_idx"
            ),
        ),
    ]
