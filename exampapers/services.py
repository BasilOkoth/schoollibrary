from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


TWO_DECIMAL_PLACES = Decimal("0.01")


def calculate_weighted_subject_result(
    *,
    student,
    exam,
    subject,
):
    components = (
        ExamSubjectComponent.objects
        .filter(
            exam=exam,
            subject=subject,
        )
        .prefetch_related("papers__student_marks")
        .order_by("order", "name")
    )

    components = list(components)

    if not components:
        raise ValidationError(
            "No assessment components have been configured."
        )

    total_weight = sum(
        (
            Decimal(component.weight_percentage)
            for component in components
        ),
        start=Decimal("0.00"),
    )

    if total_weight != Decimal("100.00"):
        raise ValidationError(
            f"Component contributions must total 100%. "
            f"The current total is {total_weight}%."
        )

    final_percentage = Decimal("0.00")
    breakdown = []

    for component in components:
        papers = list(component.papers.all())

        if not papers:
            raise ValidationError(
                f"{component.name} does not contain any papers."
            )

        raw_total = Decimal("0.00")
        maximum_total = Decimal("0.00")

        for paper in papers:
            mark = StudentPaperMark.objects.filter(
                student=student,
                paper=paper,
            ).first()

            if mark is None:
                raise ValidationError(
                    f"Missing {paper.paper_name} mark "
                    f"for {student}."
                )

            raw_total += Decimal(mark.raw_score)
            maximum_total += Decimal(paper.max_marks)

        if maximum_total <= 0:
            raise ValidationError(
                f"{component.name} has an invalid maximum."
            )

        component_percentage = (
            raw_total / maximum_total
        ) * Decimal("100")

        weighted_contribution = (
            component_percentage
            / Decimal("100")
            * Decimal(component.weight_percentage)
        )

        final_percentage += weighted_contribution

        breakdown.append(
            {
                "component": component.name,
                "raw_total": raw_total,
                "maximum_total": maximum_total,
                "weight": component.weight_percentage,
                "contribution": weighted_contribution.quantize(
                    TWO_DECIMAL_PLACES,
                    rounding=ROUND_HALF_UP,
                ),
            }
        )

    final_percentage = final_percentage.quantize(
        TWO_DECIMAL_PLACES,
        rounding=ROUND_HALF_UP,
    )

    return final_percentage, breakdown
