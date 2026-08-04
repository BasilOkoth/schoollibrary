# digitallibrary/management/commands/audit_student_subjects.py
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count, Q

from digitallibrary.models import Student


class Command(BaseCommand):
    help = (
        "Audit active learners' subject registrations in one tenant schema."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            required=True,
            help="Academic year, for example 2026 or 2026-2027.",
        )
        parser.add_argument(
            "--class-id",
            type=int,
            help="Limit the audit to one current class.",
        )
        parser.add_argument(
            "--only-problems",
            action="store_true",
            help="Display only learners with zero active registrations.",
        )

    def handle(self, *args, **options):
        schema_name = getattr(connection, "schema_name", None)

        if not schema_name or schema_name == "public":
            raise CommandError(
                "Run this command through tenant_command with --schema."
            )

        academic_year = str(options["academic_year"]).strip()

        students = Student.objects.filter(
            is_active=True,
            status="active",
        ).select_related(
            "current_class",
        ).annotate(
            registered_count=Count(
                "subjects_taken",
                filter=Q(
                    subjects_taken__academic_year=academic_year,
                    subjects_taken__is_active=True,
                ),
                distinct=True,
            ),
        ).order_by(
            "current_class__sort_order",
            "current_class__name",
            "admission_number",
        )

        if options["class_id"]:
            students = students.filter(
                current_class_id=options["class_id"]
            )

        if options["only_problems"]:
            students = students.filter(registered_count=0)

        total = 0
        without_subjects = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Schema: {schema_name}; academic year: {academic_year}"
            )
        )

        for student in students:
            total += 1

            if student.registered_count == 0:
                without_subjects += 1
                output = self.style.ERROR
                status = "NO SUBJECTS"
            else:
                output = self.style.SUCCESS
                status = f"{student.registered_count} subject(s)"

            class_name = (
                student.current_class.name
                if student.current_class
                else "No Class"
            )

            self.stdout.write(
                output(
                    f"{student.admission_number} - "
                    f"{student.get_full_name()} - "
                    f"{class_name}: {status}"
                )
            )

        self.stdout.write(
            f"Audited {total} learner(s); "
            f"{without_subjects} learner(s) have no active registration."
        )
