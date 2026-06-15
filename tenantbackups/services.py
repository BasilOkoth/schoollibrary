import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import connection
from django.utils import timezone


def _database_config():
    config = settings.DATABASES["default"]

    return {
        "name": config.get("NAME"),
        "user": config.get("USER"),
        "password": config.get("PASSWORD"),
        "host": config.get("HOST") or "localhost",
        "port": str(config.get("PORT") or "5432"),
    }


def _run_command(command, env=None):
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
    digest = hashlib.sha256()

    with open(file_path, "rb") as backup_stream:
        for chunk in iter(
            lambda: backup_stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def create_backup_file(backup):
    """
    Create one PostgreSQL custom-format dump for one tenant schema.

    The backup model record must already exist.
    """
    if backup.tenant_schema == "public":
        raise ValueError(
            "The public schema cannot be backed up "
            "using TenantBackup."
        )

    database = _database_config()

    backup.status = "running"
    backup.error_message = ""
    backup.save(
        update_fields=[
            "status",
            "error_message",
        ]
    )

    filename = (
        f"{backup.tenant_schema}_"
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
        environment["PGPASSWORD"] = (
            database["password"] or ""
        )

        command = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--schema",
            backup.tenant_schema,
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
        backup.is_verified = True
        backup.verification_message = (
            "Backup file created and checksum verified."
        )
        backup.status = "completed"
        backup.completed_at = timezone.now()
        backup.error_message = ""

        backup.save(
            update_fields=[
                "backup_file",
                "filename",
                "file_size",
                "checksum",
                "database_format",
                "is_verified",
                "verification_message",
                "status",
                "completed_at",
                "error_message",
            ]
        )

        return backup

    except Exception as error:
        backup.status = "failed"
        backup.error_message = str(error)
        backup.is_verified = False
        backup.save(
            update_fields=[
                "status",
                "error_message",
                "is_verified",
            ]
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
    Restore exactly one tenant schema from exactly one
    TenantBackup record.

    No other tenant schema is changed.
    """
    schema_name = backup.tenant_schema

    if schema_name == "public":
        raise ValueError(
            "The public schema cannot be restored here."
        )

    if backup.school.schema_name != schema_name:
        raise ValueError(
            "The backup school does not match "
            "the backup tenant schema."
        )

    verified, verification_message = verify_backup_file(
        backup
    )

    if not verified:
        raise ValueError(verification_message)

    database = _database_config()
    temporary_path = None

    restore_log.status = "running"
    restore_log.error_message = ""
    restore_log.save(
        update_fields=[
            "status",
            "error_message",
        ]
    )

    backup.status = "restoring"
    backup.error_message = ""
    backup.save(
        update_fields=[
            "status",
            "error_message",
        ]
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
        environment["PGPASSWORD"] = (
            database["password"] or ""
        )

        # Remove only the selected tenant schema.
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP SCHEMA IF EXISTS '
                f'"{schema_name}" CASCADE;'
            )
            cursor.execute(
                f'CREATE SCHEMA "{schema_name}";'
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

        restore_log.status = "completed"
        restore_log.completed_at = now
        restore_log.error_message = ""
        restore_log.save(
            update_fields=[
                "status",
                "completed_at",
                "error_message",
            ]
        )

        backup.status = "restored"
        backup.restored_at = now
        backup.restored_by = restore_log.initiated_by
        backup.error_message = ""
        backup.save(
            update_fields=[
                "status",
                "restored_at",
                "restored_by",
                "error_message",
            ]
        )

        return backup

    except Exception as error:
        restore_log.status = "failed"
        restore_log.error_message = str(error)
        restore_log.completed_at = timezone.now()
        restore_log.save(
            update_fields=[
                "status",
                "error_message",
                "completed_at",
            ]
        )

        backup.status = "failed"
        backup.error_message = str(error)
        backup.save(
            update_fields=[
                "status",
                "error_message",
            ]
        )
        raise

    finally:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
