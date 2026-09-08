# resultstreams/management/commands/repair_stream_results.py

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from digitallibrary.models import StudentResult


TWO_PLACES = Decimal("0.01")

RAW_RESULT_PATTERN = re.compile(
    r"Raw\s+result:\s*"
    r"(?P<raw>-?\d+(?:\.\d+)?)\s*/\s*"
    r"(?P<maximum>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def decimal_value(value):
    """Return a two-decimal Decimal value."""
    try:
        return Decimal(str(value)).quantize(
            TWO_PLACES,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"Invalid decimal value: {value}") from error


def extract_raw_result(remarks):
    """Extract the raw mark and maximum from a result remark."""
    match = RAW_RESULT_PATTERN.search(str(remarks or ""))

    if match is None:
        return None

    try:
        raw_score = decimal_value(match.group("raw"))
        maximum = decimal_value(match.group("maximum"))
    except ValueError:
        return None

    if maximum <= 0:
        return None

    if raw_score < 0 or raw_score > maximum:
        return None

    return raw_score, maximum


def calculate_buggy_score(raw_score, maximum):
    """Reproduce the percentage that the old buggy code stored as score."""
    return (
        raw_score
        / maximum
        * Decimal("100")
    ).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def student_display_name(student):
    """Return a readable student name."""
    get_full_name = getattr(student, "get_full_name", None)

    if callable(get_full_name):
        name = str(get_full_name() or "").strip()
        if name:
            return name

    return str(student)


class Command(BaseCommand):
    help = (
        "Repair StudentResult rows where the result-stream entry page "
        "incorrectly stored a percentage in StudentResult.score instead "
        "of the original raw examination mark."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Actually update the database. "
                "Without this option the command performs a dry run."
            ),
        )

        parser.add_argument(
            "--exam-id",
            type=int,
            help="Only inspect results belonging to this exam ID.",
        )

        parser.add_argument(
            "--subject-id",
            type=int,
            help="Only inspect results belonging to this subject ID.",
        )

        parser.add_argument(
            "--student-id",
            type=int,
            help="Only inspect results belonging to this student ID.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        exam_id = options.get("exam_id")
        subject_id = options.get("subject_id")
        student_id = options.get("student_id")

        schema_name = getattr(
            connection,
            "schema_name",
            None,
        )

        if not schema_name or schema_name == "public":
            raise CommandError(
                "Run this command inside a school tenant schema. "
                "Use: python manage.py tenant_command "
                "repair_stream_results --schema=<school_schema>"
            )

        queryset = (
            StudentResult.objects
            .filter(
                remarks__icontains="Raw result:"
            )
            .select_related(
                "student",
                "exam",
                "subject",
            )
            .order_by(
                "exam_id",
                "subject_id",
                "student_id",
            )
        )

        if exam_id:
            queryset = queryset.filter(
                exam_id=exam_id,
            )

        if subject_id:
            queryset = queryset.filter(
                subject_id=subject_id,
            )

        if student_id:
            queryset = queryset.filter(
                student_id=student_id,
            )

        total_checked = 0
        repair_candidates = 0
        repaired = 0
        already_correct = 0
        ambiguous = 0
        invalid_markers = 0

        mode = "APPLY" if apply_changes else "DRY RUN"

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Student result repair - {mode}"
            )
        )
        self.stdout.write(
            f"Tenant schema: {schema_name}"
        )
        self.stdout.write("")

        with transaction.atomic():
            for result in queryset.iterator():
                total_checked += 1

                extracted = extract_raw_result(
                    result.remarks
                )

                if extracted is None:
                    invalid_markers += 1

                    self.stdout.write(
                        self.style.WARNING(
                            (
                                f"SKIP INVALID: result #{result.id} "
                                f"{student_display_name(result.student)} "
                                f"| {result.exam} "
                                f"| {result.subject} "
                                f"| remarks={result.remarks!r}"
                            )
                        )
                    )
                    continue

                raw_score, recorded_maximum = extracted

                try:
                    current_score = decimal_value(
                        result.score
                    )
                except ValueError:
                    ambiguous += 1

                    self.stdout.write(
                        self.style.WARNING(
                            (
                                f"SKIP NO SCORE: result #{result.id} "
                                f"{student_display_name(result.student)}"
                            )
                        )
                    )
                    continue

                if current_score == raw_score:
                    already_correct += 1
                    continue

                buggy_score = calculate_buggy_score(
                    raw_score,
                    recorded_maximum,
                )

                if current_score != buggy_score:
                    ambiguous += 1

                    self.stdout.write(
                        self.style.WARNING(
                            (
                                f"SKIP AMBIGUOUS: result #{result.id} "
                                f"{student_display_name(result.student)} "
                                f"| {result.exam} "
                                f"| {result.subject} "
                                f"| current={current_score} "
                                f"| raw={raw_score}/{recorded_maximum} "
                                f"| expected buggy value={buggy_score}"
                            )
                        )
                    )
                    continue

                repair_candidates += 1

                self.stdout.write(
                    (
                        f"{'REPAIR' if apply_changes else 'WOULD REPAIR'}: "
                        f"result #{result.id} "
                        f"| {student_display_name(result.student)} "
                        f"| {result.exam} "
                        f"| {result.subject} "
                        f"| {current_score} -> {raw_score} "
                        f"(raw {raw_score}/{recorded_maximum})"
                    )
                )

                if not apply_changes:
                    continue

                result.score = raw_score

                result.save(
                    update_fields=["score"]
                )

                result.refresh_from_db()

                persisted_score = decimal_value(
                    result.score
                )

                if persisted_score != raw_score:
                    raise CommandError(
                        (
                            "Verification failed for result "
                            f"#{result.id}. Expected {raw_score}, "
                            f"but database contains {persisted_score}."
                        )
                    )

                repaired += 1

            if not apply_changes:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "Repair summary"
            )
        )
        self.stdout.write(
            f"Checked:           {total_checked}"
        )
        self.stdout.write(
            f"Repair candidates: {repair_candidates}"
        )
        self.stdout.write(
            f"Already correct:   {already_correct}"
        )
        self.stdout.write(
            f"Ambiguous/skipped: {ambiguous}"
        )
        self.stdout.write(
            f"Invalid markers:   {invalid_markers}"
        )

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully repaired: {repaired}"
                )
            )
        else:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN ONLY - no database records were changed."
                )
            )
            self.stdout.write(
                (
                    "If the proposed repairs are correct, "
                    "run the command again with --apply."
                )
            )
