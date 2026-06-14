import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from tenants.models import Tenant  # Replace with your actual tenant model


SCHEMA_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def get_database_config():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)

        return {
            "name": parsed.path.lstrip("/"),
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port or 5432,
        }

    database = settings.DATABASES["default"]

    return {
        "name": database["NAME"],
        "user": database["USER"],
        "password": database["PASSWORD"],
        "host": database.get("HOST") or "localhost",
        "port": database.get("PORT") or 5432,
    }


class Command(BaseCommand):
    help = "Restore one specified tenant schema from its backup file."

    def add_arguments(self, parser):
        parser.add_argument(
            "schema_name",
            help="Schema of the tenant that should be restored.",
        )

        parser.add_argument(
            "backup_file",
            help="Path to the tenant .dump backup file.",
        )

        parser.add_argument(
            "--confirm-schema",
            required=True,
            help="Must exactly match schema_name as a safety confirmation.",
        )

        parser.add_argument(
            "--keep-current",
            action="store_true",
            help="Do not drop the current tenant schema before restoring.",
        )

    def handle(self, *args, **options):
        schema_name = options["schema_name"].strip()
        confirmed_schema = options["confirm_schema"].strip()
        backup_path = Path(options["backup_file"]).resolve()

        if schema_name == "public":
            raise CommandError(
                "The public schema cannot be restored with this command."
            )

        if schema_name != confirmed_schema:
            raise CommandError(
                "The confirmation schema does not match the selected tenant."
            )

        if not SCHEMA_PATTERN.fullmatch(schema_name):
            raise CommandError("Invalid tenant schema name.")

        if not backup_path.exists():
            raise CommandError(
                f"Backup file was not found: {backup_path}"
            )

        if backup_path.suffix != ".dump":
            raise CommandError(
                "The selected backup must be a PostgreSQL .dump file."
            )

        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"Tenant schema '{schema_name}' is not registered."
            ) from exc

        # Verify that the dump contains the intended schema.
        list_result = subprocess.run(
            ["pg_restore", "--list", str(backup_path)],
            capture_output=True,
            text=True,
        )

        if list_result.returncode != 0:
            raise CommandError(
                f"Could not inspect the backup: {list_result.stderr}"
            )

        schema_markers = (
            f"SCHEMA - {schema_name}",
            f"TABLE {schema_name}",
            f"TABLE DATA {schema_name}",
            f"SEQUENCE {schema_name}",
        )

        if not any(
            marker in list_result.stdout for marker in schema_markers
        ):
            raise CommandError(
                f"The selected backup does not appear to contain "
                f"schema '{schema_name}'. Restore cancelled."
            )

        database = get_database_config()
        environment = os.environ.copy()

        if database["password"]:
            environment["PGPASSWORD"] = str(database["password"])

        self.stdout.write(
            self.style.WARNING(
                f"Restoring tenant '{tenant}' using schema '{schema_name}'."
            )
        )

        if not options["keep_current"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Dropping the existing schema '{schema_name}'."
                )
            )

            quoted_schema = connection.ops.quote_name(schema_name)

            with connection.cursor() as cursor:
                cursor.execute(
                    f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
                )
                cursor.execute(
                    f"CREATE SCHEMA {quoted_schema}"
                )

        command = [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--host",
            str(database["host"]),
            "--port",
            str(database["port"]),
            "--username",
            str(database["user"]),
            "--dbname",
            str(database["name"]),
            "--schema",
            schema_name,
            str(backup_path),
        ]

        result = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise CommandError(
                f"Restore failed for tenant '{schema_name}':\n"
                f"{result.stderr}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant '{schema_name}' was restored successfully."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "No other tenant schema was modified."
            )
        )
