from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0016_fix_tenantbackup_school_fk"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE
                old_constraint_name text;
            BEGIN
                SELECT con.conname
                INTO old_constraint_name
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = rel.oid
                WHERE rel.relname = 'digitallibrary_tenantbackup'
                  AND con.contype = 'f'
                  AND att.attnum = ANY(con.conkey)
                  AND att.attname = 'school_id'
                LIMIT 1;

                IF old_constraint_name IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE digitallibrary_tenantbackup DROP CONSTRAINT %I',
                        old_constraint_name
                    );
                END IF;

                ALTER TABLE digitallibrary_tenantbackup
                ADD CONSTRAINT digitallibrary_tenantbackup_school_id_tenants_school_fk
                FOREIGN KEY (school_id)
                REFERENCES tenants_school(id)
                DEFERRABLE INITIALLY DEFERRED;
            END $$;
            """,
            reverse_sql="""
            DO $$
            DECLARE
                current_constraint_name text;
            BEGIN
                SELECT con.conname
                INTO current_constraint_name
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = rel.oid
                WHERE rel.relname = 'digitallibrary_tenantbackup'
                  AND con.contype = 'f'
                  AND att.attnum = ANY(con.conkey)
                  AND att.attname = 'school_id'
                LIMIT 1;

                IF current_constraint_name IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE digitallibrary_tenantbackup DROP CONSTRAINT %I',
                        current_constraint_name
                    );
                END IF;

                ALTER TABLE digitallibrary_tenantbackup
                ADD CONSTRAINT digitallibrary_tenantbackup_school_id_digitallibrary_school_fk
                FOREIGN KEY (school_id)
                REFERENCES digitallibrary_school(id)
                DEFERRABLE INITIALLY DEFERRED;
            END $$;
            """,
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE
                old_constraint_name text;
            BEGIN
                SELECT con.conname
                INTO old_constraint_name
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = rel.oid
                WHERE rel.relname = 'digitallibrary_tenantrestorelog'
                  AND con.contype = 'f'
                  AND att.attnum = ANY(con.conkey)
                  AND att.attname = 'school_id'
                LIMIT 1;

                IF old_constraint_name IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE digitallibrary_tenantrestorelog DROP CONSTRAINT %I',
                        old_constraint_name
                    );
                END IF;

                ALTER TABLE digitallibrary_tenantrestorelog
                ADD CONSTRAINT digitallibrary_tenantrestorelog_school_id_tenants_school_fk
                FOREIGN KEY (school_id)
                REFERENCES tenants_school(id)
                DEFERRABLE INITIALLY DEFERRED;
            END $$;
            """,
            reverse_sql="""
            DO $$
            DECLARE
                current_constraint_name text;
            BEGIN
                SELECT con.conname
                INTO current_constraint_name
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = rel.oid
                WHERE rel.relname = 'digitallibrary_tenantrestorelog'
                  AND con.contype = 'f'
                  AND att.attnum = ANY(con.conkey)
                  AND att.attname = 'school_id'
                LIMIT 1;

                IF current_constraint_name IS NOT NULL THEN
                    EXECUTE format(
                        'ALTER TABLE digitallibrary_tenantrestorelog DROP CONSTRAINT %I',
                        current_constraint_name
                    );
                END IF;

                ALTER TABLE digitallibrary_tenantrestorelog
                ADD CONSTRAINT digitallibrary_tenantrestorelog_school_id_digitallibrary_school_fk
                FOREIGN KEY (school_id)
                REFERENCES digitallibrary_school(id)
                DEFERRABLE INITIALLY DEFERRED;
            END $$;
            """,
        ),
    ]
