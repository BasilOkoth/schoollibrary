# digitallibrary/management/commands/backfill_student_subjects.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q, QuerySet

from digitallibrary.models import (
    Student,
    StudentEnrollment,
    StudentEnrollmentSubject,
    StudentResult,
    StudentSubject,
    Subject,
)


@dataclass(frozen=True)
class RegistrationPlan:
    """Subject registration plan for one learner."""

    student: Student
    subjects: QuerySet[Subject]
    source_summary: str


@dataclass
class BackfillStats:
    """Backfill counters."""

    processed: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    registered_subjects: int = 0


def normalize_academic_year(value: object) -> str:
    """Return a validated academic-year value accepted by the models."""

    year = str(value or "").strip()

    if not year:
        raise CommandError("--academic-year is required.")

    if len(year) > 9:
        raise CommandError(
            "Academic year must be at most 9 characters, for example "
            "'2026' or '2026-2027'."
        )

    return year


def is_legacy_class(student_class) -> bool:
    """Return whether the class uses the legacy Form 3/Form 4 curriculum."""

    if not student_class:
        return False

    if getattr(student_class, "is_legacy", False):
        return True

    if getattr(student_class, "curriculum", "") == "LEGACY_844":
        return True

    if getattr(student_class, "level", "") == "LEGACY_SECONDARY":
        return True

    class_name = str(getattr(student_class, "name", "") or "").strip().lower()

    return any(
        marker in class_name
        for marker in (
            "form 3",
            "form three",
            "form iii",
            "form 4",
            "form four",
            "form iv",
        )
    )


def existing_registration_subject_ids(
    student: Student,
    academic_year: str,
) -> set[int]:
    """
    Return subject IDs already supported by registration or result evidence.

    Existing results are always preserved so an old mark cannot disappear from
    a report merely because formal subject registration was missing.
    """

    subject_ids = set(
        student.subjects.values_list("id", flat=True)
    )

    subject_ids.update(
        StudentSubject.objects.filter(
            student=student,
            academic_year=academic_year,
            is_active=True,
        ).values_list("subject_id", flat=True)
    )

    subject_ids.update(
        StudentEnrollmentSubject.objects.filter(
            student=student,
            academic_year=academic_year,
            is_active=True,
        ).values_list("subject_id", flat=True)
    )

    subject_ids.update(
        StudentResult.objects.filter(
            student=student,
            exam__academic_year=academic_year,
        ).values_list("subject_id", flat=True)
    )

    return {subject_id for subject_id in subject_ids if subject_id}


def build_registration_plan(
    *,
    student: Student,
    academic_year: str,
    legacy_mode: str,
) -> RegistrationPlan:
    """
    Build the expected subject set for one learner.

    Rules:
    - Primary and Junior: all active subjects attached to the class.
    - Senior: official combination plus compulsory and Mathematics subjects
      returned by Student.get_allowed_subjects().
    - Legacy Form 3/Form 4 in safe mode: compulsory subjects plus existing
      registrations and subjects with results.
    - Legacy all-class mode: every active subject attached to the class.
    """

    if not student.current_class_id:
        return RegistrationPlan(
            student=student,
            subjects=Subject.objects.none(),
            source_summary="no current class",
        )

    class_subjects = Subject.objects.filter(
        applicable_classes=student.current_class,
        is_active=True,
    ).distinct()

    evidence_ids = existing_registration_subject_ids(
        student=student,
        academic_year=academic_year,
    )

    if getattr(student.current_class, "requires_pathway", False):
        allowed_ids = set(
            student.get_allowed_subjects().values_list("id", flat=True)
        )
        allowed_ids.update(evidence_ids)

        return RegistrationPlan(
            student=student,
            subjects=Subject.objects.filter(
                id__in=allowed_ids,
                is_active=True,
            ).distinct().order_by(
                "result_code",
                "category",
                "order",
                "name",
            ),
            source_summary="official Senior combination plus existing evidence",
        )

    if is_legacy_class(student.current_class):
        if legacy_mode == "all-class":
            expected_ids = set(
                class_subjects.values_list("id", flat=True)
            )
            expected_ids.update(evidence_ids)
            source_summary = "all class subjects plus existing evidence"
        else:
            compulsory_ids = set(
                class_subjects.filter(
                    Q(is_compulsory=True)
                    | Q(category="compulsory")
                ).values_list("id", flat=True)
            )
            expected_ids = compulsory_ids | evidence_ids
            source_summary = (
                "compulsory subjects plus existing registrations/results"
            )

        return RegistrationPlan(
            student=student,
            subjects=Subject.objects.filter(
                id__in=expected_ids,
                is_active=True,
            ).distinct().order_by(
                "result_code",
                "category",
                "order",
                "name",
            ),
            source_summary=source_summary,
        )

    expected_ids = set(
        class_subjects.values_list("id", flat=True)
    )
    expected_ids.update(evidence_ids)

    return RegistrationPlan(
        student=student,
        subjects=Subject.objects.filter(
            id__in=expected_ids,
            is_active=True,
        ).distinct().order_by(
            "result_code",
            "category",
            "order",
            "name",
        ),
        source_summary="all class subjects plus existing evidence",
    )


def get_or_sync_enrollment(
    *,
    student: Student,
    academic_year: str,
) -> StudentEnrollment:
    """Create or align the learner's enrollment for the selected year."""

    StudentEnrollment.objects.filter(
        student=student,
        is_current=True,
    ).exclude(
        academic_year=academic_year,
    ).update(
        is_current=False,
        status=StudentEnrollment.STATUS_INACTIVE,
    )

    enrollment, _ = StudentEnrollment.objects.get_or_create(
        student=student,
        academic_year=academic_year,
        defaults={
            "student_class": student.current_class,
            "stream": student.stream,
            "pathway": student.pathway or "",
            "is_current": True,
            "status": StudentEnrollment.STATUS_ACTIVE,
        },
    )

    changed_fields: list[str] = []

    if enrollment.student_class_id != student.current_class_id:
        enrollment.student_class = student.current_class
        changed_fields.append("student_class")

    if enrollment.stream_id != student.stream_id:
        enrollment.stream = student.stream
        changed_fields.append("stream")

    expected_pathway = student.pathway or ""
    if (enrollment.pathway or "") != expected_pathway:
        enrollment.pathway = expected_pathway
        changed_fields.append("pathway")

    if not enrollment.is_current:
        enrollment.is_current = True
        changed_fields.append("is_current")

    if enrollment.status != StudentEnrollment.STATUS_ACTIVE:
        enrollment.status = StudentEnrollment.STATUS_ACTIVE
        changed_fields.append("status")

    if changed_fields:
        changed_fields.append("updated_at")
        enrollment.save(update_fields=changed_fields)

    return enrollment


def synchronize_registration(
    *,
    plan: RegistrationPlan,
    academic_year: str,
) -> int:
    """Synchronize all three subject-registration stores."""

    student = plan.student
    subjects = list(plan.subjects)
    subject_ids = {subject.id for subject in subjects}

    student.subjects.set(subjects)

    StudentSubject.objects.filter(
        student=student,
        academic_year=academic_year,
    ).exclude(
        subject_id__in=subject_ids,
    ).update(is_active=False)

    for subject in subjects:
        StudentSubject.objects.update_or_create(
            student=student,
            subject=subject,
            academic_year=academic_year,
            defaults={"is_active": True},
        )

    enrollment = get_or_sync_enrollment(
        student=student,
        academic_year=academic_year,
    )

    StudentEnrollmentSubject.objects.filter(
        enrollment=enrollment,
    ).exclude(
        subject_id__in=subject_ids,
    ).update(is_active=False)

    for subject in subjects:
        StudentEnrollmentSubject.objects.update_or_create(
            enrollment=enrollment,
            subject=subject,
            defaults={
                "student": student,
                "academic_year": academic_year,
                "is_active": True,
            },
        )

    return len(subjects)


def format_subject_names(subjects: Iterable[Subject]) -> str:
    """Format a compact subject list for command output."""

    names = [subject.name for subject in subjects]
    return ", ".join(names) if names else "none"


class Command(BaseCommand):
    help = (
        "Backfill student subject registrations in the active tenant schema. "
        "Run through django-tenants tenant_command."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--academic-year",
            required=True,
            help="Academic year, for example 2026 or 2026-2027.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the planned registrations without changing data.",
        )
        parser.add_argument(
            "--student-id",
            type=int,
            action="append",
            dest="student_ids",
            help=(
                "Limit to one learner ID. Repeat the option for multiple "
                "learners."
            ),
        )
        parser.add_argument(
            "--class-id",
            type=int,
            help="Limit the command to one current class.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive learners.",
        )
        parser.add_argument(
            "--legacy-mode",
            choices=("safe", "all-class"),
            default="safe",
            help=(
                "safe: Form 3/Form 4 receive compulsory subjects plus existing "
                "registrations/results. all-class: register every subject "
                "attached to the legacy class."
            ),
        )

    def handle(self, *args, **options):
        schema_name = getattr(connection, "schema_name", None)

        if not schema_name or schema_name == "public":
            raise CommandError(
                "Run this command inside one tenant schema, for example: "
                "python manage.py tenant_command backfill_student_subjects "
                "--schema=demo --academic-year=2026 --dry-run"
            )

        academic_year = normalize_academic_year(
            options["academic_year"]
        )
        dry_run = options["dry_run"]
        legacy_mode = options["legacy_mode"]

        students = Student.objects.select_related(
            "current_class",
            "stream",
            "subject_combination",
            "subject_combination__pathway",
        ).prefetch_related(
            "subjects",
        ).order_by(
            "current_class__sort_order",
            "current_class__name",
            "admission_number",
        )

        if not options["include_inactive"]:
            students = students.filter(
                is_active=True,
                status="active",
            )

        if options["class_id"]:
            students = students.filter(
                current_class_id=options["class_id"]
            )

        if options["student_ids"]:
            students = students.filter(
                id__in=options["student_ids"]
            )

        stats = BackfillStats()

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Schema: {schema_name}; academic year: {academic_year}; "
                f"legacy mode: {legacy_mode}; dry run: {dry_run}"
            )
        )

        for student in students.iterator(chunk_size=200):
            stats.processed += 1

            if not student.current_class_id:
                stats.skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP {student.admission_number}: no current class"
                    )
                )
                continue

            try:
                plan = build_registration_plan(
                    student=student,
                    academic_year=academic_year,
                    legacy_mode=legacy_mode,
                )
                planned_subjects = list(plan.subjects)

                if not planned_subjects:
                    stats.skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIP {student.admission_number} "
                            f"({student.current_class}): no subjects found; "
                            f"source={plan.source_summary}"
                        )
                    )
                    continue

                if self.verbosity >= 2 or dry_run:
                    self.stdout.write(
                        f"{'PLAN' if dry_run else 'APPLY'} "
                        f"{student.admission_number} - "
                        f"{student.get_full_name()} - "
                        f"{student.current_class}: "
                        f"{format_subject_names(planned_subjects)}"
                    )

                if dry_run:
                    stats.updated += 1
                    stats.registered_subjects += len(planned_subjects)
                    continue

                with transaction.atomic():
                    registered_count = synchronize_registration(
                        plan=plan,
                        academic_year=academic_year,
                    )

                stats.updated += 1
                stats.registered_subjects += registered_count

            except Exception as error:
                stats.failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"FAIL {student.admission_number}: {error}"
                    )
                )

        summary = (
            f"processed={stats.processed}, updated={stats.updated}, "
            f"skipped={stats.skipped}, failed={stats.failed}, "
            f"subject registrations={stats.registered_subjects}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN COMPLETE: {summary}")
            )
        elif stats.failed:
            self.stdout.write(
                self.style.WARNING(f"COMPLETE WITH ERRORS: {summary}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"COMPLETE: {summary}")
            )
