from django.db import migrations


DROP_AND_RECREATE_TENANTBACKUP_FK = """
DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT con.conname
    INTO constraint_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_attribute att ON att.attrelid = rel.oid
    WHERE rel.relname = 'digitallibrary_tenantbackup'
      AND con.contype = 'f'
      AND att.attnum = ANY(con.conkey)
      AND att.attname = 'school_id'
    LIMIT 1;

    IF constraint_name IS NOT NULL THEN
        EXECUTE format(
            '
