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
    """Exact subject registration plan for one learner."""

    student: Student
    subjects: QuerySet[Subject]
    source_summary: str
    warning: str = ""
    skip: bool = False


@dataclass
class BackfillStats:
    """Backfill counters."""

    processed: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    registered_subjects: int = 0
    warnings: int = 0


def normalize_academic_year(value: object) -> str:
    """Validate an academic-year value accepted by the models."""

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
    """Return whether a class uses the legacy Form 3/Form 4 curriculum."""

    if not student_class:
        return False

    if getattr(student_class, "is_legacy", False):
        return True

    if getattr(student_class, "curriculum", "") == "LEGACY_844":
        return True

    if getattr(student_class, "level", "") == "LEGACY_SECONDARY":
        return True

    class_name = str(
        getattr(student_class, "name", "") or ""
    ).strip().lower()

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


def is_mathematics_option(subject: Subject) -> bool:
    """Identify Core or Essential Mathematics subjects."""

    code = str(subject.code or "").strip().lower()
    name = str(subject.name or "").strip().lower()

    return (
        code in {
            "core_math",
            "core_mathematics",
            "essential_math",
            "essential_mathematics",
        }
        or name in {
            "core mathematics",
            "essential mathematics",
        }
    )


def selected_mathematics_subject(
    *,
    student: Student,
    class_subjects: QuerySet[Subject],
) -> Subject | None:
    """Resolve exactly one Mathematics option for a Senior learner."""

    option = str(
        getattr(student, "mathematics_option", "") or ""
    ).strip().lower()

    if option == "core":
        return class_subjects.filter(
            Q(code__iexact="CORE_MATH")
            | Q(code__iexact="CORE_MATHEMATICS")
            | Q(name__iexact="Core Mathematics")
        ).first()

    if option == "essential":
        return class_subjects.filter(
            Q(code__iexact="ESSENTIAL_MATH")
            | Q(code__iexact="ESSENTIAL_MATHEMATICS")
            | Q(name__iexact="Essential Mathematics")
        ).first()

    combination = getattr(student, "subject_combination", None)

    if combination:
        resolved = str(
            getattr(
                combination,
                "resolved_mathematics_option",
                "",
            )
            or ""
        ).strip().lower()

        if resolved == "core":
            return class_subjects.filter(
                Q(code__iexact="CORE_MATH")
                | Q(code__iexact="CORE_MATHEMATICS")
                | Q(name__iexact="Core Mathematics")
            ).first()

        if resolved == "essential":
            return class_subjects.filter(
                Q(code__iexact="ESSENTIAL_MATH")
                | Q(code__iexact="ESSENTIAL_MATHEMATICS")
                | Q(name__iexact="Essential Mathematics")
            ).first()

    return None


def result_subject_ids(
    *,
    student: Student,
    academic_year: str,
) -> set[int]:
    """Preserve subjects that already have marks for legacy learners."""

    return {
        subject_id
        for subject_id in StudentResult.objects.filter(
            student=student,
            exam__academic_year=academic_year,
        ).values_list("subject_id", flat=True)
        if subject_id
    }


def existing_registration_subject_ids(
    *,
    student: Student,
    academic_year: str,
) -> set[int]:
    """Return active registration evidence for non-Senior backfills."""

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

    return {subject_id for subject_id in subject_ids if subject_id}


def ordered_subject_queryset(subject_ids: set[int]) -> QuerySet[Subject]:
    """Return active subjects in report-card order."""

    return Subject.objects.filter(
        id__in=subject_ids,
        is_active=True,
    ).distinct().order_by(
        "result_code",
        "category",
        "order",
        "name",
    )


def build_senior_registration_plan(
    *,
    student: Student,
    class_subjects: QuerySet[Subject],
    without_combination: str,
) -> RegistrationPlan:
    """
    Build an exact Grade 10–12 registration.

    Existing M2M registrations are deliberately ignored because they may
    contain subjects inherited from a former class or pathway.
    """

    common_compulsory_ids = {
        subject.id
        for subject in class_subjects.filter(
            is_compulsory=True,
        )
        if not is_mathematics_option(subject)
    }

    mathematics = selected_mathematics_subject(
        student=student,
        class_subjects=class_subjects,
    )

    if mathematics:
        common_compulsory_ids.add(mathematics.id)

    combination = getattr(student, "subject_combination", None)

    if not combination:
        if without_combination == "skip":
            return RegistrationPlan(
                student=student,
                subjects=Subject.objects.none(),
                source_summary="Senior combination missing",
                warning=(
                    "Official Senior subject combination is not assigned."
                ),
                skip=True,
            )

        warning = (
            "Official Senior subject combination is missing; only common "
            "compulsory subjects and the selected Mathematics option will "
            "be registered."
        )

        return RegistrationPlan(
            student=student,
            subjects=ordered_subject_queryset(
                common_compulsory_ids
            ),
            source_summary=(
                "common compulsory subjects plus selected Mathematics"
            ),
            warning=warning,
        )

    combination_ids = set(
        combination.ordered_subjects.values_list(
            "id",
            flat=True,
        )
    )

    selected_ids = common_compulsory_ids | combination_ids

    if mathematics:
        for subject in class_subjects:
            if (
                is_mathematics_option(subject)
                and subject.id != mathematics.id
            ):
                selected_ids.discard(subject.id)

    return RegistrationPlan(
        student=student,
        subjects=ordered_subject_queryset(selected_ids),
        source_summary=(
            f"official combination {combination.code} plus common "
            "compulsory subjects"
        ),
    )


def build_registration_plan(
    *,
    student: Student,
    academic_year: str,
    legacy_mode: str,
    senior_without_combination: str,
) -> RegistrationPlan:
    """Build the expected subject set for one learner."""

    if not student.current_class_id:
        return RegistrationPlan(
            student=student,
            subjects=Subject.objects.none(),
            source_summary="no current class",
            warning="The learner has no current class.",
            skip=True,
        )

    class_subjects = Subject.objects.filter(
        applicable_classes=student.current_class,
        is_active=True,
    ).distinct()

    if getattr(student.current_class, "requires_pathway", False):
        return build_senior_registration_plan(
            student=student,
            class_subjects=class_subjects,
            without_combination=senior_without_combination,
        )

    results = result_subject_ids(
        student=student,
        academic_year=academic_year,
    )

    if is_legacy_class(student.current_class):
        existing = existing_registration_subject_ids(
            student=student,
            academic_year=academic_year,
        )

        if legacy_mode == "all-class":
            expected_ids = set(
                class_subjects.values_list("id", flat=True)
            )
            expected_ids.update(results)
            expected_ids.update(existing)
            source_summary = (
                "all legacy class subjects plus existing "
                "registrations/results"
            )
        else:
            compulsory_ids = set(
                class_subjects.filter(
                    Q(is_compulsory=True)
                    | Q(category="compulsory")
                ).values_list("id", flat=True)
            )
            expected_ids = compulsory_ids | results | existing
            source_summary = (
                "compulsory legacy class subjects plus existing "
                "registrations/results"
            )

        warning = ""

        if not class_subjects.exists():
            warning = (
                f"{student.current_class} has no active applicable subjects. "
                "Only existing registrations/results can be preserved."
            )

        return RegistrationPlan(
            student=student,
            subjects=ordered_subject_queryset(expected_ids),
            source_summary=source_summary,
            warning=warning,
        )

    expected_ids = set(
        class_subjects.values_list("id", flat=True)
    )
    expected_ids.update(results)

    return RegistrationPlan(
        student=student,
        subjects=ordered_subject_queryset(expected_ids),
        source_summary="all active class subjects plus existing results",
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
    """Synchronize every subject-registration store exactly."""

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
        "Backfill exact student subject registrations in the active tenant "
        "schema. Run through django-tenants tenant_command."
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
            help="Show the exact plan without changing data.",
        )
        parser.add_argument(
            "--student-id",
            type=int,
            action="append",
            dest="student_ids",
            help="Limit to one learner ID; repeat for multiple learners.",
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
            default="all-class",
            help=(
                "all-class (default): Form 3/Form 4 receive every subject "
                "configured for the legacy class, plus existing results/"
                "registrations. safe: keep only compulsory class subjects "
                "plus existing registrations/results."
            ),
        )
        parser.add_argument(
            "--senior-without-combination",
            choices=("skip", "compulsory"),
            default="skip",
            help=(
                "skip: do not change Grade 10–12 learners without an official "
                "combination. compulsory: register only common compulsory "
                "subjects and the selected Mathematics option."
            ),
        )

    def handle(self, *args, **options):
        schema_name = getattr(connection, "schema_name", None)

        if not schema_name or schema_name == "public":
            raise CommandError(
                "Run this inside one tenant schema, for example: "
                "python manage.py tenant_command backfill_student_subjects "
                "--schema=demo --academic-year=2026 --dry-run"
            )

        academic_year = normalize_academic_year(
            options["academic_year"]
        )
        dry_run = options["dry_run"]

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
                f"Schema: {schema_name}; year: {academic_year}; "
                f"legacy mode: {options['legacy_mode']}; "
                f"Senior without combination: "
                f"{options['senior_without_combination']}; "
                f"dry run: {dry_run}"
            )
        )

        for student in students.iterator(chunk_size=200):
            stats.processed += 1

            try:
                plan = build_registration_plan(
                    student=student,
                    academic_year=academic_year,
                    legacy_mode=options["legacy_mode"],
                    senior_without_combination=options[
                        "senior_without_combination"
                    ],
                )

                if plan.warning:
                    stats.warnings += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"WARN {student.admission_number}: "
                            f"{plan.warning}"
                        )
                    )

                if plan.skip:
                    stats.skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIP {student.admission_number} - "
                            f"{student.get_full_name()}: "
                            f"{plan.source_summary}"
                        )
                    )
                    continue

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

                if options["verbosity"] >= 2 or dry_run:
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
            f"warnings={stats.warnings}, "
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
