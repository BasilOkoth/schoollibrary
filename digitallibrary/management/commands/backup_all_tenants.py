import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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
    help = "Back up every tenant schema into a separate PostgreSQL dump file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="tenant_backups",
            help="Directory where tenant backup folders will be stored.",
        )

    def handle(self, *args, **options):
        database = get_database_config()

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        root_directory = Path(options["output_dir"]).resolve()
        backup_directory = root_directory / timestamp
        backup_directory.mkdir(parents=True, exist_ok=True)

        tenants = Tenant.objects.exclude(schema_name="public").order_by(
            "schema_name"
        )

        if not tenants.exists():
            raise CommandError("No tenant schemas were found.")

        environment = os.environ.copy()

        if database["password"]:
            environment["PGPASSWORD"] = str(database["password"])

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": database["name"],
            "backup_type": "tenant_schema_backups",
            "tenants": [],
        }

        successful = 0
        failed = 0

        for tenant in tenants:
            schema_name = tenant.schema_name

            if not SCHEMA_PATTERN.fullmatch(schema_name):
                self.stderr.write(
                    self.style.ERROR(
                        f"Skipped invalid schema name: {schema_name}"
                    )
                )
                failed += 1
                continue

            filename = f"{schema_name}_{timestamp}.dump"
            output_path = backup_directory / filename

            command = [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--verbose",
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
                "--file",
                str(output_path),
            ]

            self.stdout.write(f"Backing up tenant: {schema_name}")

            result = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                failed += 1

                manifest["tenants"].append(
                    {
                        "schema_name": schema_name,
                        "status": "failed",
                        "error": result.stderr,
                    }
                )

                self.stderr.write(
                    self.style.ERROR(
                        f"Backup failed for {schema_name}: {result.stderr}"
                    )
                )
                continue

            successful += 1

            manifest["tenants"].append(
                {
                    "schema_name": schema_name,
                    "tenant_id": tenant.pk,
                    "backup_file": filename,
                    "size_bytes": output_path.stat().st_size,
                    "status": "successful",
                }
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Backup completed: {schema_name} → {filename}"
                )
            )

        manifest_path = backup_directory / "manifest.json"

        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Backup run completed. Successful: {successful}; "
                f"Failed: {failed}"
            )
        )
        self.stdout.write(f"Backup directory: {backup_directory}")
        self.stdout.write(f"Manifest: {manifest_path}")
