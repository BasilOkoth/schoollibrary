from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "digitallibrary",
            "0013_tenantbackup_tenantrestorelog_and_more",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS digitallibrary_tenantbackup (
                id uuid PRIMARY KEY,
                tenant_schema varchar(63) NOT NULL,
                tenant_name varchar(200) NOT NULL,
                backup_type varchar(20) NOT NULL DEFAULT 'manual',
                status varchar(20) NOT NULL DEFAULT 'pending',
                backup_file varchar(500),
                filename varchar(255) NOT NULL DEFAULT '',
                file_size bigint NOT NULL DEFAULT 0,
                checksum varchar(64) NOT NULL DEFAULT '',
                database_format varchar(20) NOT NULL DEFAULT 'postgres_custom',
                includes_media boolean NOT NULL DEFAULT false,
                is_verified boolean NOT NULL DEFAULT false,
                verification_message text NOT NULL DEFAULT '',
                error_message text NOT NULL DEFAULT '',
                created_at timestamp with time zone NOT NULL DEFAULT now(),
                completed_at timestamp with time zone,
                restored_at timestamp with time zone,
                notes text NOT NULL DEFAULT '',
                school_id integer NOT NULL,
                created_by_id integer,
                restored_by_id integer
            );

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantbackup_schema_created_idx
                ON digitallibrary_tenantbackup (tenant_schema, created_at DESC);

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantbackup_school_created_idx
                ON digitallibrary_tenantbackup (school_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantbackup_status_idx
                ON digitallibrary_tenantbackup (status);

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantbackup_type_idx
                ON digitallibrary_tenantbackup (backup_type);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS digitallibrary_tenantbackup CASCADE;
            """,
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS digitallibrary_tenantrestorelog (
                id uuid PRIMARY KEY,
                tenant_schema varchar(63) NOT NULL,
                status varchar(20) NOT NULL DEFAULT 'pending',
                started_at timestamp with time zone NOT NULL DEFAULT now(),
                completed_at timestamp with time zone,
                error_message text NOT NULL DEFAULT '',
                ip_address inet,
                backup_id uuid NOT NULL,
                school_id integer NOT NULL,
                initiated_by_id integer
            );

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantrestorelog_schema_started_idx
                ON digitallibrary_tenantrestorelog (tenant_schema, started_at DESC);

            CREATE INDEX IF NOT EXISTS digitallibrary_tenantrestorelog_status_idx
                ON digitallibrary_tenantrestorelog (status);
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS digitallibrary_tenantrestorelog CASCADE;
            """,
        ),
    ]
