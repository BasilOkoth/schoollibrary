import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context


VALID_SCHEMA_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _set_search_path(schema_name):
    """
    Explicitly set PostgreSQL search_path to the tenant schema.
    This ensures queries use the correct schema even if schema_context
    does not fully set the search path.
    """
    if schema_name and schema_name != "public":
        with connection.cursor() as cursor:
            cursor.execute(
                f'SET search_path TO "{schema_name}", public;'
            )


def _validate_schema_name(schema_name):
    """
    Prevent accidental public-schema operations and unsafe schema names.
    """
    schema_name = str(schema_name or "").strip()

    if not schema_name:
        raise ValueError("Tenant schema is missing.")

    if schema_name == "public":
        raise ValueError(
            "The public schema cannot be backed up or restored here."
        )

    if not VALID_SCHEMA_RE.match(schema_name):
        raise ValueError(
            f"Unsafe tenant schema name: {schema_name}"
        )

    return schema_name


def _database_config():
    """
    Return database connection settings for pg_dump and pg_restore.
    """
    config = settings.DATABASES["default"]

    return {
        "name": config.get("NAME"),
        "user": config.get("USER"),
        "password": config.get("PASSWORD") or "",
        "host": config.get("HOST") or "localhost",
        "port": str(config.get("PORT") or "5432"),
    }


def _ensure_command_exists(command_name):
    """
    Make the error clearer if Render does not have pg_dump/pg_restore.
    """
    if not shutil.which(command_name):
        raise RuntimeError(
            f"{command_name} was not found in the server environment. "
            "Install PostgreSQL client tools on Render before using backups."
        )


def _run_command(command, env=None):
    """
    Run a shell command safely and raise a useful error when it fails.
    """
    process = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        error = (
            process.stderr
            or process.stdout
            or "Database command failed."
        )
        raise RuntimeError(error.strip())

    return process


def _sha256(file_path):
    """
    Calculate SHA-256 checksum for a file.
    """
    digest = hashlib.sha256()

    with open(file_path, "rb") as backup_stream:
        for chunk in iter(
            lambda: backup_stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _model_has_field(model_class, field_name):
    """
    Check whether a model has a given field.
    """
    return any(
        field.name == field_name
        for field in model_class._meta.fields
    )


def _clean_update_fields(model_class, update_values):
    """
    Remove fields that do not exist on the model.
    This prevents update() from failing if a field is optional/missing.
    """
    valid_field_names = {
        field.name
        for field in model_class._meta.fields
    }

    return {
        key: value
        for key, value in update_values.items()
        if key in valid_field_names
    }


def _refresh_instance_from_db(instance):
    """
    Refresh an ORM instance if the row still exists.
    During restore, the schema can be dropped/recreated, so the row may not exist.
    """
    try:
        instance.refresh_from_db()
    except Exception:
        pass

    return instance


def _safe_tenant_update(model_class, schema_name, pk, **update_values):
    """
    Safely update a row in a tenant schema.

    This avoids:
        Save with update_fields did not affect any rows.

    That error happens when Django tries to save an old ORM object after
    the schema has been switched, dropped, recreated, or restored.
    """
    schema_name = _validate_schema_name(schema_name)

    if not pk:
        return 0

    clean_values = _clean_update_fields(
        model_class,
        update_values,
    )

    if not clean_values:
        return 0

    with schema_context(schema_name):
        _set_search_path(schema_name)

        return (
            model_class.objects
            .filter(pk=pk)
            .update(**clean_values)
        )


def _save_backup_status(backup, fields):
    """
    Safely save TenantBackup fields in the tenant schema.

    The TenantBackup table exists inside each tenant schema, not public.
    This function avoids backup.save(update_fields=...), because restore
    operations can make the current backup object stale.
    """
    schema_name = _validate_schema_name(backup.tenant_schema)

    update_values = {
        field: getattr(backup, field)
        for field in fields
        if hasattr(backup, field)
    }

    updated = _safe_tenant_update(
        backup.__class__,
        schema_name,
        backup.pk,
        **update_values,
    )

    if updated:
        _refresh_instance_from_db(backup)

    return updated


def _save_restore_log_status(restore_log, fields):
    """
    Safely save TenantRestoreLog fields in the tenant schema.

    The TenantRestoreLog table exists inside each tenant schema, not public.
    This function avoids restore_log.save(update_fields=...), because restore
    operations can make the current restore_log object stale.
    """
    schema_name = _validate_schema_name(restore_log.tenant_schema)

    update_values = {
        field: getattr(restore_log, field)
        for field in fields
        if hasattr(restore_log, field)
    }

    updated = _safe_tenant_update(
        restore_log.__class__,
        schema_name,
        restore_log.pk,
        **update_values,
    )

    if updated:
        _refresh_instance_from_db(restore_log)

    return updated


def create_backup_file(backup):
    """
    Create one PostgreSQL custom-format dump for one tenant schema.

    This function creates a backup for the single tenant attached
    to the TenantBackup record. It does not back up all tenants
    into one file.
    """
    schema_name = _validate_schema_name(backup.tenant_schema)

    _set_search_path(schema_name)

    _ensure_command_exists("pg_dump")

    database = _database_config()

    backup.status = "running"
    backup.error_message = ""
    backup.is_verified = False

    _save_backup_status(
        backup,
        [
            "status",
            "error_message",
            "is_verified",
        ],
    )

    filename = (
        f"{schema_name}_"
        f"{timezone.now():%Y%m%d_%H%M%S}_"
        f"{backup.id}.dump"
    )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".dump",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name

        environment = os.environ.copy()
        environment["PGPASSWORD"] = database["password"]

        command = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--schema",
            schema_name,
            "--file",
            temporary_path,
            "--host",
            database["host"],
            "--port",
            database["port"],
            "--username",
            database["user"],
            database["name"],
        ]

        _run_command(
            command,
            env=environment,
        )

        checksum = _sha256(temporary_path)
        file_size = Path(temporary_path).stat().st_size

        with open(temporary_path, "rb") as backup_stream:
            backup.backup_file.save(
                filename,
                File(backup_stream),
                save=False,
            )

        backup.filename = filename
        backup.file_size = file_size
        backup.checksum = checksum
        backup.database_format = "postgres_custom"
        backup.includes_media = False
        backup.is_verified = True
        backup.verification_message = (
            "Backup file created and checksum verified."
        )
        backup.status = "completed"
        backup.completed_at = timezone.now()
        backup.error_message = ""

        _save_backup_status(
            backup,
            [
                "backup_file",
                "filename",
                "file_size",
                "checksum",
                "database_format",
                "includes_media",
                "is_verified",
                "verification_message",
                "status",
                "completed_at",
                "error_message",
            ],
        )

        return backup

    except Exception as error:
        backup.status = "failed"
        backup.error_message = str(error)
        backup.is_verified = False

        _save_backup_status(
            backup,
            [
                "status",
                "error_message",
                "is_verified",
            ],
        )

        raise

    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass


def verify_backup_file(backup):
    """
    Verify that the stored backup file exists and matches
    the saved SHA-256 checksum.
    """
    if not backup.backup_file:
        return False, "Backup file is missing."

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".dump",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name

            for chunk in backup.backup_file.chunks():
                temporary_file.write(chunk)

        current_checksum = _sha256(temporary_path)

        if not backup.checksum:
            return False, "Stored checksum is missing."

        if current_checksum != backup.checksum:
            return False, "Backup checksum does not match."

        return True, "Backup checksum verified."

    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass


def restore_backup_file(backup, restore_log):
    """
    Restore exactly one tenant schema from exactly one TenantBackup.

    This function only drops and recreates backup.tenant_schema.
    It does not restore all tenants and does not touch public.
    """
    schema_name = _validate_schema_name(backup.tenant_schema)

    _set_search_path(schema_name)

    _ensure_command_exists("pg_restore")

    if backup.school.schema_name != schema_name:
        raise ValueError(
            "The backup school does not match the backup tenant schema."
        )

    if restore_log.tenant_schema != schema_name:
        raise ValueError(
            "The restore log tenant schema does not match the backup."
        )

    if restore_log.backup_id != backup.id:
        raise ValueError(
            "The restore log is not attached to this backup."
        )

    verified, verification_message = verify_backup_file(backup)

    if not verified:
        raise ValueError(verification_message)

    database = _database_config()
    temporary_path = None

    restore_log_pk = restore_log.pk
    backup_pk = backup.pk

    restore_log.status = "running"
    restore_log.error_message = ""

    _save_restore_log_status(
        restore_log,
        [
            "status",
            "error_message",
        ],
    )

    backup.status = "restoring"
    backup.error_message = ""

    _save_backup_status(
        backup,
        [
            "status",
            "error_message",
        ],
    )

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".dump",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name

            for chunk in backup.backup_file.chunks():
                temporary_file.write(chunk)

        environment = os.environ.copy()
        environment["PGPASSWORD"] = database["password"]

        quoted_schema_name = connection.ops.quote_name(schema_name)

        # Remove and recreate only the selected tenant schema.
        with connection.cursor() as cursor:
            cursor.execute(
                f"DROP SCHEMA IF EXISTS {quoted_schema_name} CASCADE;"
            )
            cursor.execute(
                f"CREATE SCHEMA {quoted_schema_name};"
            )

        command = [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--schema",
            schema_name,
            "--host",
            database["host"],
            "--port",
            database["port"],
            "--username",
            database["user"],
            "--dbname",
            database["name"],
            temporary_path,
        ]

        _run_command(
            command,
            env=environment,
        )

        now = timezone.now()

        # The restore has dropped/recreated the tenant schema.
        # Re-query rows instead of saving old ORM objects.
        _safe_tenant_update(
            restore_log.__class__,
            schema_name,
            restore_log_pk,
            status="completed",
            completed_at=now,
            error_message="",
        )

        _safe_tenant_update(
            backup.__class__,
            schema_name,
            backup_pk,
            status="restored",
            restored_at=now,
            restored_by=getattr(restore_log, "initiated_by", None),
            error_message="",
        )

        with schema_context(schema_name):
            _set_search_path(schema_name)

            try:
                restored_backup = (
                    backup.__class__.objects
                    .filter(pk=backup_pk)
                    .first()
                )
                return restored_backup or backup
            except Exception:
                return backup

    except Exception as error:
        # After a failed restore, the schema may be in a partial state.
        # Do not call save(update_fields=...) on stale ORM objects.
        try:
            _safe_tenant_update(
                restore_log.__class__,
                schema_name,
                restore_log_pk,
                status="failed",
                error_message=str(error),
                completed_at=timezone.now(),
            )
        except Exception:
            pass

        try:
            _safe_tenant_update(
                backup.__class__,
                schema_name,
                backup_pk,
                status="failed",
                error_message=str(error),
            )
        except Exception:
            pass

        raise

    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
