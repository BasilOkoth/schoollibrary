import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from digitallibrary.views import _import_official_combination_row


class Command(BaseCommand):
    help = (
        "Import official Senior School subject combinations from CSV. "
        "Run inside a tenant schema, for example through tenant_command."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the official combination CSV file.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])

        if not csv_path.exists():
            raise CommandError(
                f"CSV file does not exist: {csv_path}"
            )

        success_count = 0
        failure_count = 0

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)

            required_columns = {
                "code",
                "pathway",
                "track",
                "subject_1",
                "subject_2",
                "subject_3",
            }

            missing_columns = (
                required_columns
                - set(reader.fieldnames or [])
            )

            if missing_columns:
                raise CommandError(
                    (
                        "Missing required CSV columns: "
                        + ", ".join(sorted(missing_columns))
                    )
                )

            for row_number, row in enumerate(
                reader,
                start=2,
            ):
                if not any(
                    str(value or "").strip()
                    for value in row.values()
                ):
                    continue

                try:
                    combination = (
                        _import_official_combination_row(row)
                    )
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            (
                                f"Row {row_number}: "
                                f"{combination.code} imported."
                            )
                        )
                    )
                except Exception as error:
                    failure_count += 1
                    self.stderr.write(
                        self.style.ERROR(
                            (
                                f"Row {row_number} "
                                f"({row.get('code', '')}): "
                                f"{error}"
                            )
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Finished: {success_count} imported, "
                    f"{failure_count} rejected."
                )
            )
        )

        if failure_count:
            raise CommandError(
                (
                    f"{failure_count} row(s) failed validation. "
                    "Correct the CSV and import again."
                )
            )
