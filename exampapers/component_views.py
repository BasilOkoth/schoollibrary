import re
from decimal import (
    Decimal,
    InvalidOperation,
)

from django.contrib import messages
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from digitallibrary.decorators import (
    tenant_and_role_required,
)
from digitallibrary.models import (
    Exam,
    Subject,
)

from .models import (
    ExamSubjectComponent,
    ExamSubjectPaper,
    StudentPaperMark,
)
from .views import (
    RESULT_ENTRY_ROLES,
    get_schema_name,
    get_tenant_base_url,
)


ONE_HUNDRED = Decimal("100.00")

SAFE_KEY = re.compile(
    r"^[A-Za-z0-9_-]+$"
)


def decimal_or_error(
    value,
    label,
    errors,
):
    try:
        return Decimal(
            str(value)
        ).quantize(
            Decimal("0.01")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        errors.append(
            f"Enter a valid {label}."
        )

        return None


def parse_configuration(
    request,
):
    component_keys = (
        request.POST.getlist(
            "component_key"
        )
    )

    component_names = (
        request.POST.getlist(
            "component_name"
        )
    )

    component_weights = (
        request.POST.getlist(
            "component_weight"
        )
    )

    component_orders = (
        request.POST.getlist(
            "component_order"
        )
    )

    paper_component_keys = (
        request.POST.getlist(
            "paper_component_key"
        )
    )

    paper_names = (
        request.POST.getlist(
            "paper_name"
        )
    )

    paper_maximums = (
        request.POST.getlist(
            "paper_max_marks"
        )
    )

    paper_orders = (
        request.POST.getlist(
            "paper_order"
        )
    )

    errors = []
    rows = []
    row_map = {}
    used_names = set()
    total_weight = Decimal("0.00")

    component_count = max(
        len(component_keys),
        len(component_names),
        len(component_weights),
        len(component_orders),
        0,
    )

    for index in range(
        component_count
    ):
        key = (
            component_keys[index]
            if index
            < len(component_keys)
            else ""
        )

        name = (
            component_names[index]
            if index
            < len(component_names)
            else ""
        )

        weight_text = (
            component_weights[index]
            if index
            < len(component_weights)
            else ""
        )

        order_text = (
            component_orders[index]
            if index
            < len(component_orders)
            else str(index + 1)
        )

        key = (
            key or ""
        ).strip()

        name = (
            name or ""
        ).strip()

        weight_text = (
            weight_text or ""
        ).strip()

        order_text = (
            order_text or ""
        ).strip()

        if (
            not key
            or not SAFE_KEY.match(key)
        ):
            errors.append(
                f"Component {index + 1} "
                "has an invalid identifier."
            )

            continue

        row = {
            "key": key,
            "name": name,
            "weight_percentage": (
                weight_text
            ),
            "order": (
                order_text
                or str(index + 1)
            ),
            "papers": [],
        }

        rows.append(
            row
        )

        row_map[key] = row

        if not name:
            errors.append(
                f"Component {index + 1}: "
                "enter a name."
            )

        else:
            normalized_name = (
                name.casefold()
            )

            if (
                normalized_name
                in used_names
            ):
                errors.append(
                    f"The component '{name}' "
                    "has been entered more "
                    "than once."
                )

            used_names.add(
                normalized_name
            )

        weight = decimal_or_error(
            weight_text,
            (
                f"contribution for "
                f"{name or 'component'}"
            ),
            errors,
        )

        if weight is not None:
            if (
                weight <= 0
                or weight > ONE_HUNDRED
            ):
                errors.append(
                    f"{name or 'Component'}: "
                    "contribution must be "
                    "greater than 0 and no "
                    "more than 100."
                )

            else:
                total_weight += weight

        try:
            order_number = int(
                order_text
                or index + 1
            )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                f"{name or 'Component'}: "
                "enter a valid order."
            )

        else:
            if order_number < 1:
                errors.append(
                    f"{name or 'Component'}: "
                    "order must be at least 1."
                )

    paper_count = max(
        len(paper_component_keys),
        len(paper_names),
        len(paper_maximums),
        len(paper_orders),
        0,
    )

    used_papers = {}

    for index in range(
        paper_count
    ):
        component_key = (
            paper_component_keys[index]
            if index
            < len(paper_component_keys)
            else ""
        )

        paper_name = (
            paper_names[index]
            if index
            < len(paper_names)
            else ""
        )

        maximum_text = (
            paper_maximums[index]
            if index
            < len(paper_maximums)
            else ""
        )

        order_text = (
            paper_orders[index]
            if index
            < len(paper_orders)
            else str(index + 1)
        )

        component_key = (
            component_key or ""
        ).strip()

        paper_name = (
            paper_name or ""
        ).strip()

        maximum_text = (
            maximum_text or ""
        ).strip()

        order_text = (
            order_text or ""
        ).strip()

        component_row = (
            row_map.get(
                component_key
            )
        )

        if component_row is None:
            errors.append(
                f"Paper row {index + 1} "
                "does not belong to a valid "
                "component."
            )

            continue

        paper_row = {
            "paper_name": paper_name,
            "max_marks": maximum_text,
            "order": (
                order_text
                or str(index + 1)
            ),
        }

        component_row[
            "papers"
        ].append(
            paper_row
        )

        if not paper_name:
            errors.append(
                f"{component_row['name']}: "
                "enter a paper name."
            )

        normalized_paper = (
            paper_name.casefold()
        )

        component_used = (
            used_papers.setdefault(
                component_key,
                set(),
            )
        )

        if (
            paper_name
            and normalized_paper
            in component_used
        ):
            errors.append(
                f"{component_row['name']}: "
                f"'{paper_name}' has been "
                "entered more than once."
            )

        component_used.add(
            normalized_paper
        )

        maximum = decimal_or_error(
            maximum_text,
            (
                f"maximum for "
                f"{paper_name or 'paper'}"
            ),
            errors,
        )

        if maximum is not None:
            if maximum <= 0:
                errors.append(
                    f"{paper_name or 'Paper'}: "
                    "maximum must be greater "
                    "than zero."
                )

            if maximum > Decimal(
                "1000.00"
            ):
                errors.append(
                    f"{paper_name or 'Paper'}: "
                    "maximum cannot exceed "
                    "1000."
                )

        try:
            order_number = int(
                order_text
                or index + 1
            )

        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                f"{paper_name or 'Paper'}: "
                "enter a valid order."
            )

        else:
            if order_number < 1:
                errors.append(
                    f"{paper_name or 'Paper'}: "
                    "order must be at least 1."
                )

    if not rows:
        errors.append(
            "Configure at least one "
            "assessment component."
        )

    for row in rows:
        if not row["papers"]:
            errors.append(
                f"{row['name'] or 'Component'} "
                "must contain at least one "
                "paper."
            )

    if (
        rows
        and total_weight
        != ONE_HUNDRED
    ):
        errors.append(
            "Component contributions must "
            "total exactly 100%. "
            f"The current total is "
            f"{total_weight}%."
        )

    return (
        rows,
        errors,
        total_weight,
    )


def existing_rows(
    components,
):
    rows = []

    for component in components:
        rows.append(
            {
                "key": (
                    f"component_"
                    f"{component.id}"
                ),
                "name": (
                    component.name
                ),
                "weight_percentage": (
                    component
                    .weight_percentage
                ),
                "order": (
                    component.order
                ),
                "papers": [
                    {
                        "paper_name": (
                            paper.paper_name
                        ),
                        "max_marks": (
                            paper.max_marks
                        ),
                        "order": (
                            paper.order
                        ),
                    }
                    for paper
                    in component.papers.all()
                ],
            }
        )

    return rows


@tenant_and_role_required(
    RESULT_ENTRY_ROLES
)
def configure_components(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
):
    exam = get_object_or_404(
        Exam.objects.select_related(
            "student_class"
        ),
        pk=exam_id,
    )

    subject = get_object_or_404(
        Subject,
        pk=subject_id,
        is_active=True,
    )

    components = list(
        ExamSubjectComponent.objects
        .filter(
            exam=exam,
            subject=subject,
        )
        .prefetch_related(
            "papers",
        )
        .order_by(
            "order",
            "name",
        )
    )

    has_marks = (
        StudentPaperMark.objects
        .filter(
            paper__component__exam=exam,
            paper__component__subject=(
                subject
            ),
        )
        .exists()
    )

    submitted_rows = None
    page_errors = []
    total_weight = Decimal("0.00")

    if request.method == "POST":
        if has_marks:
            messages.error(
                request,
                "The configuration is locked "
                "because pupil marks already "
                "exist."
            )

            return redirect(
                request.path
            )

        (
            submitted_rows,
            page_errors,
            total_weight,
        ) = parse_configuration(
            request
        )

        if not page_errors:
            try:
                with transaction.atomic():
                    (
                        ExamSubjectComponent
                        .objects
                        .filter(
                            exam=exam,
                            subject=subject,
                        )
                        .delete()
                    )

                    for row in submitted_rows:
                        component = (
                            ExamSubjectComponent
                            .objects
                            .create(
                                exam=exam,
                                subject=subject,
                                name=row["name"],
                                weight_percentage=(
                                    Decimal(
                                        row[
                                            "weight_percentage"
                                        ]
                                    )
                                ),
                                order=int(
                                    row["order"]
                                ),
                                created_by=(
                                    request.user
                                ),
                            )
                        )

                        for paper_row in row[
                            "papers"
                        ]:
                            (
                                ExamSubjectPaper
                                .objects
                                .create(
                                    component=(
                                        component
                                    ),
                                    paper_name=(
                                        paper_row[
                                            "paper_name"
                                        ]
                                    ),
                                    max_marks=(
                                        Decimal(
                                            paper_row[
                                                "max_marks"
                                            ]
                                        )
                                    ),
                                    order=int(
                                        paper_row[
                                            "order"
                                        ]
                                    ),
                                    created_by=(
                                        request.user
                                    ),
                                )
                            )

            except Exception as error:
                page_errors.append(
                    str(error)
                )

            else:
                messages.success(
                    request,
                    "Weighted assessment "
                    "configuration saved."
                )

                class_id = (
                    request.POST.get(
                        "class_id"
                    )
                    or exam.student_class_id
                )

                destination = (
                    f"{get_tenant_base_url(request, tenant_schema)}"
                    f"/exam-papers/results/"
                    f"{exam.id}/"
                    f"{subject.id}/"
                )

                if class_id:
                    destination += (
                        f"?class_id={class_id}"
                    )

                return redirect(
                    destination
                )

    if submitted_rows is not None:
        component_rows = (
            submitted_rows
        )

    elif components:
        component_rows = existing_rows(
            components
        )

        total_weight = sum(
            (
                Decimal(
                    component
                    .weight_percentage
                )
                for component
                in components
            ),
            start=Decimal("0.00"),
        )

    else:
        component_rows = [
            {
                "key": "component_1",
                "name": "Overall",
                "weight_percentage": (
                    "100.00"
                ),
                "order": 1,
                "papers": [
                    {
                        "paper_name": (
                            "Paper 1"
                        ),
                        "max_marks": (
                            "100.00"
                        ),
                        "order": 1,
                    }
                ],
            }
        ]

        total_weight = Decimal(
            "100.00"
        )

    return render(
        request,
        (
            "exampapers/"
            "configure_components.html"
        ),
        {
            "exam": exam,
            "subject": subject,
            "component_rows": (
                component_rows
            ),
            "existing_components": (
                components
            ),
            "has_marks": has_marks,
            "page_errors": page_errors,
            "total_weight": (
                total_weight
            ),
            "tenant_schema": (
                get_schema_name(
                    request,
                    tenant_schema,
                )
            ),
            "tenant_base_url": (
                get_tenant_base_url(
                    request,
                    tenant_schema,
                )
            ),
            "class_id": (
                request.GET.get(
                    "class_id"
                )
                or request.POST.get(
                    "class_id"
                )
                or exam.student_class_id
            ),
        },
    )
