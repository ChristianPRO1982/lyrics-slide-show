# Generated manually for shared common group tables.

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app_animation", "0013_animation_remote_connection"),
        ("app_group", "0002_groups_common_state"),
    ]

    operations = [
        migrations.RunSQL(
            sql=r"""
                DO $$
                DECLARE
                    stale_fk record;
                BEGIN
                    FOR stale_fk IN
                        SELECT con.conname
                        FROM pg_constraint AS con
                        JOIN pg_attribute AS att
                          ON att.attrelid = con.conrelid
                         AND att.attnum = ANY(con.conkey)
                        WHERE con.contype = 'f'
                          AND con.conrelid = 'lss.a_animations'::regclass
                          AND att.attname = 'group_id'
                          AND con.conname <> 'a_animations_group_common_fk'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE lss.a_animations DROP CONSTRAINT %I',
                            stale_fk.conname
                        );
                    END LOOP;

                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'a_animations_group_common_fk'
                          AND conrelid = 'lss.a_animations'::regclass
                    ) THEN
                        ALTER TABLE lss.a_animations
                          ADD CONSTRAINT a_animations_group_common_fk
                          FOREIGN KEY (group_id)
                          REFERENCES common.g_groups (group_id)
                          ON DELETE CASCADE
                          NOT VALID;
                    END IF;

                    ALTER TABLE lss.a_animations
                      VALIDATE CONSTRAINT a_animations_group_common_fk;
                END;
                $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
