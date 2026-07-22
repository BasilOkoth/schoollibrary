from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from digitallibrary.models import StudentResult
from digitallibrary.result_grading import (
    build_student_result_defaults,
)

from .models import (
    ExamSubjectComponent,
    ExamSubjectPaper,
    StudentPaperMark,
)


TWO_DECIMAL_PLACES = Decimal("0.01")
ONE_HUNDRED = Decimal("100.00")


class PaperMarkError(ValidationError):
    pass


@dataclass(frozen=True)
class ComponentScore:
    name: str
    raw_total: Decimal
    maximum_total: Decimal
    weight_percentage: Decimal
    contribution: Decimal


@dataclass(frozen=True)
class CalculatedSubjectScore:
    raw_total: Decimal
    maximum_total: Decimal
    percentage: Decimal
    breakdown: tuple[ComponentScore, ...] = ()


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


def get_configured_components(
    exam,
    subject,
):
    return (
        ExamSubjectComponent.objects
        .filter(
            exam=exam,
            subject=subject,
        )
        .prefetch_related("papers")
        .order_by(
            "order",
            "name",
        )
    )


def get_configured_papers(
    exam,
    subject,
):
    return (
        ExamSubjectPaper.objects
        .filter(
            component__exam=exam,
            component__subject=subject,
        )
        .select_related(
            "component",
        )
        .order_by(
            "component__order",
            "component__name",
            "order",
            "paper_name",
        )
    )


def validate_component_configuration(
    components,
    papers,
):
    if not components:
        raise PaperMarkError(
            "No assessment components have been configured."
        )

    total_weight = sum(
        (
            decimal_value(
                component.weight_percentage,
                label=f"weight for {component.name}",
            )
            for component in components
        ),
        start=Decimal("0.00"),
    )

    if total_weight != ONE_HUNDRED:
        raise PaperMarkError(
            "Component contributions must total exactly 100%. "
            f"The current total is {total_weight}%."
        )

    papers_by_component = {
        component.id: []
        for component in components
    }

    for paper in papers:
        papers_by_component.setdefault(
            paper.component_id,
            [],
        ).append(paper)

    for component in components:
        if not papers_by_component.get(component.id):
            raise PaperMarkError(
                f"{component.name} does not contain any papers."
            )

    return papers_by_component


def calculate_weighted_score(
    *,
    components,
    papers,
    scores_by_paper_id,
):
    papers_by_component = validate_component_configuration(
        components,
        papers,
    )

    raw_total = Decimal("0.00")
    maximum_total = Decimal("0.00")
    final_percentage = Decimal("0.00")
    breakdown = []

    for component in components:
        component_papers = papers_by_component[
            component.id
        ]

        component_raw_total = Decimal("0.00")
        component_maximum_total = Decimal("0.00")

        for paper in component_papers:
            if paper.id not in scores_by_paper_id:
                raise PaperMarkError(
                    f"Missing {paper.paper_name} mark."
                )

            raw_score = decimal_value(
                scores_by_paper_id[paper.id],
                label=f"mark for {paper.paper_name}",
            )

            maximum = decimal_value(
                paper.max_marks,
                label=f"maximum for {paper.paper_name}",
            )

            if raw_score < 0:
                raise PaperMarkError(
                    f"{paper.paper_name} cannot be below zero."
                )

            if raw_score > maximum:
                raise PaperMarkError(
                    f"{paper.paper_name} cannot exceed {maximum}."
                )

            component_raw_total += raw_score
            component_maximum_total += maximum

        if component_maximum_total <= 0:
            raise PaperMarkError(
                f"{component.name} has an invalid maximum."
            )

        weight = decimal_value(
            component.weight_percentage,
            label=f"weight for {component.name}",
        )

        contribution = (
            component_raw_total
            / component_maximum_total
            * weight
        ).quantize(
            TWO_DECIMAL_PLACES,
            rounding=ROUND_HALF_UP,
        )

        raw_total += component_raw_total
        maximum_total += component_maximum_total
        final_percentage += contribution

        breakdown.append(
            ComponentScore(
                name=component.name,
                raw_total=component_raw_total,
                maximum_total=component_maximum_total,
                weight_percentage=weight,
                contribution=contribution,
            )
        )

    final_percentage = final_percentage.quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )

    if final_percentage < 0 or final_percentage > ONE_HUNDRED:
        raise PaperMarkError(
            "The calculated final result must be between 0 and 100."
        )

    return CalculatedSubjectScore(
        raw_total=raw_total,
        maximum_total=maximum_total,
        percentage=final_percentage,
        breakdown=tuple(breakdown),
    )


def calculate_existing_subject_score(
    student,
    exam,
    subject,
):
    components = list(
        get_configured_components(
            exam=exam,
            subject=subject,
        )
    )

    papers = list(
        get_configured_papers(
            exam=exam,
            subject=subject,
        )
    )

    if not components or not papers:
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

    scores_by_paper_id = {
        paper.id: existing_marks[paper.id].raw_score
        for paper in papers
    }

    return calculate_weighted_score(
        components=components,
        papers=papers,
        scores_by_paper_id=scores_by_paper_id,
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
    Save all raw paper marks for one pupil and calculate the final
    result using weighted assessment components.
    """

    components = list(
        ExamSubjectComponent.objects
        .select_for_update()
        .filter(
            exam=exam,
            subject=subject,
        )
        .order_by(
            "order",
            "name",
        )
    )

    papers = list(
        ExamSubjectPaper.objects
        .select_for_update()
        .filter(
            component__exam=exam,
            component__subject=subject,
        )
        .select_related(
            "component",
        )
        .order_by(
            "component__order",
            "component__name",
            "order",
            "paper_name",
        )
    )

    if not components or not papers:
        raise PaperMarkError(
            "No weighted assessment configuration exists "
            "for this subject."
        )

    expected_paper_ids = {
        paper.id
        for paper in papers
    }

    try:
        submitted_paper_ids = {
            int(paper_id)
            for paper_id in marks_by_paper_id.keys()
        }
    except (
        TypeError,
        ValueError,
    ) as error:
        raise PaperMarkError(
            "One or more submitted paper identifiers are invalid."
        ) from error

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

    validated_scores = {}

    for paper in papers:
        raw_score = decimal_value(
            marks_by_paper_id[paper.id],
            label=f"mark for {paper.paper_name}",
        )

        maximum = decimal_value(
            paper.max_marks,
            label=f"maximum for {paper.paper_name}",
        )

        if raw_score < 0:
            raise PaperMarkError(
                f"{paper.paper_name} cannot be below zero."
            )

        if raw_score > maximum:
            raise PaperMarkError(
                f"{paper.paper_name} cannot exceed {maximum}."
            )

        validated_scores[paper.id] = raw_score

        StudentPaperMark.objects.update_or_create(
            student=student,
            paper=paper,
            defaults={
                "raw_score": raw_score,
                "entered_by": entered_by,
            },
        )

    calculated = calculate_weighted_score(
        components=components,
        papers=papers,
        scores_by_paper_id=validated_scores,
    )

    breakdown_text = "; ".join(
        (
            f"{item.name}: "
            f"{item.raw_total}/{item.maximum_total} "
            f"× {item.weight_percentage}% "
            f"= {item.contribution}"
        )
        for item in calculated.breakdown
    )

    remarks = (
        f"{breakdown_text}; "
        f"Final={calculated.percentage}/100"
    )

    result_defaults = build_student_result_defaults(
        score=calculated.percentage,
        percentage_score=calculated.percentage,
        school_class=getattr(
            student,
            "current_class",
            None,
        ),
        exam=exam,
        subject=subject,
        user=entered_by,
        extra_remarks=remarks,
    )

    result, _created = (
        StudentResult.objects.update_or_create(
            student=student,
            exam=exam,
            subject=subject,
            defaults=result_defaults,
        )
    )

    result.refresh_from_db()

    return result, calculated
