from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from digitallibrary.models import StudentResult

from .models import ExamSubjectPaper, StudentPaperMark


TWO_DECIMAL_PLACES = Decimal("0.01")


class PaperMarkError(ValidationError):
    pass


@dataclass(frozen=True)
class CalculatedSubjectScore:
    raw_total: Decimal
    maximum_total: Decimal
    percentage: Decimal


def decimal_value(value, label="mark"):
    try:
        return Decimal(str(value)).quantize(
            TWO_DECIMAL_PLACES,
            rounding=ROUND_HALF_UP,
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as error:
        raise PaperMarkError(
            f"Enter a valid {label}."
        ) from error


def normalize_to_percentage(
    raw_total,
    maximum_total,
):
    raw_total = decimal_value(
        raw_total,
        label="raw total",
    )

    maximum_total = decimal_value(
        maximum_total,
        label="maximum total",
    )

    if maximum_total <= 0:
        raise PaperMarkError(
            "The combined maximum marks must be "
            "greater than zero."
        )

    if raw_total < 0:
        raise PaperMarkError(
            "The combined raw mark cannot be negative."
        )

    if raw_total > maximum_total:
        raise PaperMarkError(
            "The combined raw mark cannot exceed "
            "the combined maximum."
        )

    percentage = (
        raw_total
        / maximum_total
        * Decimal("100")
    )

    return percentage.quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )


def get_configured_papers(
    exam,
    subject,
):
    return (
        ExamSubjectPaper.objects
        .filter(
            exam=exam,
            subject=subject,
        )
        .order_by(
            "order",
            "paper_name",
        )
    )


def calculate_existing_subject_score(
    student,
    exam,
    subject,
):
    papers = list(
        get_configured_papers(
            exam=exam,
            subject=subject,
        )
    )

    if not papers:
        return None

    existing_marks = {
        mark.paper_id: mark
        for mark in StudentPaperMark.objects.filter(
            student=student,
            paper__in=papers,
        )
    }

    if len(existing_marks) != len(papers):
        return None

    raw_total = sum(
        (
            Decimal(
                existing_marks[paper.id].raw_score
            )
            for paper in papers
        ),
        start=Decimal("0.00"),
    )

    maximum_total = sum(
        (
            Decimal(paper.max_marks)
            for paper in papers
        ),
        start=Decimal("0.00"),
    )

    percentage = normalize_to_percentage(
        raw_total,
        maximum_total,
    )

    return CalculatedSubjectScore(
        raw_total=raw_total,
        maximum_total=maximum_total,
        percentage=percentage,
    )


@transaction.atomic
def save_student_paper_marks(
    student,
    exam,
    subject,
    marks_by_paper_id,
    entered_by,
):
    """
    Save all paper marks for one pupil.

    After saving, calculate:

        sum of marks obtained
        --------------------- × 100
        sum of maximum marks

    The final percentage is saved in StudentResult.score.
    """

    papers = list(
        ExamSubjectPaper.objects
        .select_for_update()
        .filter(
            exam=exam,
            subject=subject,
        )
        .order_by(
            "order",
            "paper_name",
        )
    )

    if not papers:
        raise PaperMarkError(
            "No papers have been configured for this subject."
        )

    expected_paper_ids = {
        paper.id
        for paper in papers
    }

    submitted_paper_ids = {
        int(paper_id)
        for paper_id in marks_by_paper_id.keys()
    }

    missing_paper_ids = (
        expected_paper_ids
        - submitted_paper_ids
    )

    unknown_paper_ids = (
        submitted_paper_ids
        - expected_paper_ids
    )

    if missing_paper_ids:
        missing_names = [
            paper.paper_name
            for paper in papers
            if paper.id in missing_paper_ids
        ]

        raise PaperMarkError(
            "Enter marks for every paper. Missing: "
            + ", ".join(missing_names)
        )

    if unknown_paper_ids:
        raise PaperMarkError(
            "One or more submitted papers do not belong "
            "to this exam and subject."
        )

    raw_total = Decimal("0.00")
    maximum_total = Decimal("0.00")

    for paper in papers:
        raw_score = decimal_value(
            marks_by_paper_id[paper.id],
            label=f"mark for {paper.paper_name}",
        )

        maximum = Decimal(paper.max_marks)

        if raw_score < 0:
            raise PaperMarkError(
                f"{paper.paper_name} cannot be below zero."
            )

        if raw_score > maximum:
            raise PaperMarkError(
                f"{paper.paper_name} cannot exceed "
                f"{maximum}."
            )

        StudentPaperMark.objects.update_or_create(
            student=student,
            paper=paper,
            defaults={
                "raw_score": raw_score,
                "entered_by": entered_by,
            },
        )

        raw_total += raw_score
        maximum_total += maximum

    percentage = normalize_to_percentage(
        raw_total,
        maximum_total,
    )

    calculated = CalculatedSubjectScore(
        raw_total=raw_total,
        maximum_total=maximum_total,
        percentage=percentage,
    )

    result, created = (
        StudentResult.objects.update_or_create(
            student=student,
            exam=exam,
            subject=subject,
            defaults={
                "score": percentage,
                "entered_by": entered_by,
                "remarks": (
                    f"Calculated from {len(papers)} "
                    f"paper(s): "
                    f"{raw_total}/{maximum_total}"
                ),
            },
        )
    )

    result.refresh_from_db()

    return result, calculated
