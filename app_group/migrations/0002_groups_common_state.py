# Generated manually for shared common group tables.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app_group", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="group",
                    name="g_groups_status_check",
                ),
                migrations.RemoveConstraint(
                    model_name="group",
                    name="g_groups_name_unique",
                ),
                migrations.RemoveIndex(
                    model_name="group",
                    name="g_groups_status_idx",
                ),
                migrations.RemoveIndex(
                    model_name="groupmembership",
                    name="g_grp_usr_is_admin_idx",
                ),
                migrations.AlterModelTable(
                    name="group",
                    table='common"."g_groups',
                ),
                migrations.AlterModelTable(
                    name="groupmembership",
                    table='common"."g_group_user',
                ),
                migrations.AlterModelTable(
                    name="groupjoinrequest",
                    table='common"."g_group_user_ask_to_join',
                ),
                migrations.AddField(
                    model_name="groupmembership",
                    name="am_access",
                    field=models.BooleanField(default=False, editable=False),
                ),
                migrations.AlterModelOptions(
                    name="group",
                    options={"managed": False},
                ),
                migrations.AlterModelOptions(
                    name="groupmembership",
                    options={"managed": False},
                ),
                migrations.AlterModelOptions(
                    name="groupjoinrequest",
                    options={"managed": False},
                ),
            ],
        ),
    ]
