from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from digitallibrary.decorators import (
    tenant_and_role_required,
)
from digitallibrary.models import (
    Class,
    Exam,
    Student,
    StudentResult,
    Subject,
)

from .models import (
    ExamSubjectPaper,
    StudentPaperMark,
)
from .services import (
    PaperMarkError,
    calculate_existing_subject_score,
    get_configured_papers,
    save_student_paper_marks,
)


RESULT_ENTRY_ROLES = [
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
    "teacher",
    "class_teacher",
]


def get_schema_name(
    request,
    tenant_schema=None,
):
    schema_name = (
        tenant_schema
        or getattr(
            request,
            "tenant_schema",
            None,
        )
        or getattr(
            getattr(
                request,
                "tenant",
                None,
            ),
            "schema_name",
            None,
        )
        or getattr(
            connection,
            "schema_name",
            None,
        )
    )

    if (
        not schema_name
        or schema_name == "public"
    ):
        path_parts = (
            request.path
            .strip("/")
            .split("/")
        )

        if (
            len(path_parts) >= 2
            and path_parts[0] == "tenant"
        ):
            schema_name = path_parts[1]

    return schema_name


def get_tenant_base_url(
    request,
    tenant_schema=None,
):
    schema_name = get_schema_name(
        request,
        tenant_schema,
    )

    if (
        not schema_name
        or schema_name == "public"
    ):
        return ""

    return (
        f"/tenant/{schema_name}/app"
    )


def get_active_students(
    selected_class,
):
    return (
        Student.objects
        .filter(
            current_class=selected_class,
            is_active=True,
        )
        .select_related(
            "current_class",
        )
        .order_by(
            "admission_number",
            "last_name",
            "first_name",
        )
    )


def parse_paper_configuration(request):
    paper_names = request.POST.getlist(
        "paper_name"
    )

    maximum_marks = request.POST.getlist(
        "max_marks"
    )

    paper_orders = request.POST.getlist(
        "paper_order"
    )

    largest_length = max(
        len(paper_names),
        len(maximum_marks),
        len(paper_orders),
        0,
    )

    rows = []
    errors = []
    used_names = set()

    for index in range(largest_length):
        paper_name = (
            paper_names[index]
            if index < len(paper_names)
            else ""
        )

        max_marks = (
            maximum_marks[index]
            if index < len(maximum_marks)
            else ""
        )

        order_value = (
            paper_orders[index]
            if index < len(paper_orders)
            else ""
        )

        paper_name = (
            paper_name or ""
        ).strip()

        max_marks = (
            max_marks or ""
        ).strip()

        order_value = (
            order_value or ""
        ).strip()

        if (
            not paper_name
            and not max_marks
            and not order_value
        ):
            continue

        row = {
            "paper_name": paper_name,
            "max_marks": max_marks,
            "order": (
                order_value
                or str(index + 1)
            ),
        }

        rows.append(row)

        if not paper_name:
            errors.append(
                f"Row {index + 1}: enter a paper name."
            )
            continue

        normalized_name = (
            paper_name.casefold()
        )

        if normalized_name in used_names:
            errors.append(
                f"The paper name '{paper_name}' "
                f"has been entered more than once."
            )
        else:
            used_names.add(normalized_name)

        try:
            maximum = Decimal(max_marks)
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            errors.append(
                f"{paper_name}: enter valid maximum marks."
            )
        else:
            if maximum <= 0:
                errors.append(
                    f"{paper_name}: maximum marks "
                    f"must be greater than zero."
                )

            if maximum > Decimal("1000"):
                errors.append(
                    f"{paper_name}: maximum marks "
                    f"cannot exceed 1000."
                )

        try:
            order_number = int(
                order_value
                or index + 1
            )
        except (
            TypeError,
            ValueError,
        ):
            errors.append(
                f"{paper_name}: enter a valid display order."
            )
        else:
            if order_number < 1:
                errors.append(
                    f"{paper_name}: display order "
                    f"must be at least 1."
                )

    if not rows:
        errors.append(
            "Configure at least one paper."
        )

    return rows, errors


@tenant_and_role_required(
    RESULT_ENTRY_ROLES
)
def configure_papers(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
):
    exam = get_object_or_404(
        Exam.objects.select_related(
            "student_class",
        ),
        pk=exam_id,
    )

    subject = get_object_or_404(
        Subject,
        pk=subject_id,
        is_active=True,
    )

    existing_papers = list(
        ExamSubjectPaper.objects.filter(
            exam=exam,
            subject=subject,
        ).order_by(
            "order",
            "paper_name",
        )
    )

    has_marks = (
        StudentPaperMark.objects.filter(
            paper__exam=exam,
            paper__subject=subject,
        ).exists()
    )

    submitted_rows = None
    page_errors = []

    if request.method == "POST":
        if has_marks:
            messages.error(
                request,
                "The paper configuration is locked because "
                "pupil marks have already been entered."
            )

            return redirect(
                request.path
            )

        submitted_rows, page_errors = (
            parse_paper_configuration(
                request
            )
        )

        if not page_errors:
            try:
                with transaction.atomic():
                    ExamSubjectPaper.objects.filter(
                        exam=exam,
                        subject=subject,
                    ).delete()

                    for row in submitted_rows:
                        ExamSubjectPaper.objects.create(
                            exam=exam,
                            subject=subject,
                            paper_name=(
                                row["paper_name"]
                            ),
                            max_marks=Decimal(
                                row["max_marks"]
                            ),
                            order=int(
                                row["order"]
                            ),
                            created_by=request.user,
                        )
            except Exception as error:
                page_errors.append(
                    str(error)
                )
            else:
                messages.success(
                    request,
                    (
                        f"Paper configuration saved "
                        f"for {subject.name}."
                    ),
                )

                class_id = (
                    request.POST.get(
                        "class_id"
                    )
                    or exam.student_class_id
                )

                results_url = (
                    f"{get_tenant_base_url(request, tenant_schema)}"
                    f"/exam-papers/results/"
                    f"{exam.id}/{subject.id}/"
                )

                if class_id:
                    results_url += (
                        f"?class_id={class_id}"
                    )

                return redirect(
                    results_url
                )

    if submitted_rows is not None:
        paper_rows = submitted_rows
    else:
        paper_rows = [
            {
                "paper_name": paper.paper_name,
                "max_marks": paper.max_marks,
                "order": paper.order,
            }
            for paper in existing_papers
        ]

        if not has_marks:
            number_of_blank_rows = (
                3
                if not paper_rows
                else 1
            )

            for _index in range(
                number_of_blank_rows
            ):
                paper_rows.append(
                    {
                        "paper_name": "",
                        "max_marks": "",
                        "order": (
                            len(paper_rows)
                            + 1
                        ),
                    }
                )

    configured_total = sum(
        (
            Decimal(paper.max_marks)
            for paper in existing_papers
        ),
        start=Decimal("0.00"),
    )

    context = {
        "exam": exam,
        "subject": subject,
        "paper_rows": paper_rows,
        "existing_papers": existing_papers,
        "has_marks": has_marks,
        "page_errors": page_errors,
        "configured_total": configured_total,
        "tenant_schema": get_schema_name(
            request,
            tenant_schema,
        ),
        "tenant_base_url": get_tenant_base_url(
            request,
            tenant_schema,
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
    }

    return render(
        request,
        "exampapers/configure_papers.html",
        context,
    )


@tenant_and_role_required(
    RESULT_ENTRY_ROLES
)
def enter_paper_marks(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
):
    exam = get_object_or_404(
        Exam.objects.select_related(
            "student_class",
        ),
        pk=exam_id,
    )

    subject = get_object_or_404(
        Subject,
        pk=subject_id,
        is_active=True,
    )

    class_id = (
        request.GET.get(
            "class_id"
        )
        or request.POST.get(
            "class_id"
        )
        or exam.student_class_id
    )

    if not class_id:
        messages.error(
            request,
            "Select a class before entering results."
        )

        return redirect(
            f"{get_tenant_base_url(request, tenant_schema)}"
            f"/enter-results-form/"
            f"?exam={exam.id}"
            f"&subject={subject.id}"
        )

    selected_class = get_object_or_404(
        Class,
        pk=class_id,
    )

    if (
        exam.student_class_id
        and exam.student_class_id
        != selected_class.id
    ):
        messages.error(
            request,
            "This exam belongs to a different class."
        )

        return redirect(
            f"{get_tenant_base_url(request, tenant_schema)}"
            f"/enter-results-form/"
            f"?exam={exam.id}"
        )

    papers = list(
        get_configured_papers(
            exam=exam,
            subject=subject,
        )
    )

    if not papers:
        messages.info(
            request,
            (
                f"No papers have been configured "
                f"for {subject.name}."
            ),
        )

        return redirect(
            f"{get_tenant_base_url(request, tenant_schema)}"
            f"/exam-papers/configure/"
            f"{exam.id}/{subject.id}/"
            f"?class_id={selected_class.id}"
        )

    students = list(
        get_active_students(
            selected_class
        )
    )

    if request.method == "POST":
        saved_count = 0
        skipped_count = 0
        error_messages = []

        for student in students:
            submitted_marks = {
                paper.id: (
                    request.POST.get(
                        f"mark_{student.id}_{paper.id}",
                        "",
                    )
                    or ""
                ).strip()
                for paper in papers
            }

            entered_values = [
                value
                for value in submitted_marks.values()
                if value != ""
            ]

            if not entered_values:
                continue

            if (
                len(entered_values)
                != len(papers)
            ):
                skipped_count += 1

                error_messages.append(
                    (
                        f"{student.get_full_name()}: "
                        f"enter marks for all "
                        f"{len(papers)} papers."
                    )
                )

                continue

            try:
                save_student_paper_marks(
                    student=student,
                    exam=exam,
                    subject=subject,
                    marks_by_paper_id=(
                        submitted_marks
                    ),
                    entered_by=request.user,
                )
            except PaperMarkError as error:
                skipped_count += 1

                message = (
                    error.messages[0]
                    if getattr(
                        error,
                        "messages",
                        None,
                    )
                    else str(error)
                )

                error_messages.append(
                    (
                        f"{student.get_full_name()}: "
                        f"{message}"
                    )
                )
            except Exception as error:
                skipped_count += 1

                error_messages.append(
                    (
                        f"{student.get_full_name()}: "
                        f"{error}"
                    )
                )
            else:
                saved_count += 1

        if saved_count:
            messages.success(
                request,
                (
                    f"Paper marks saved for "
                    f"{saved_count} pupil(s)."
                ),
            )

        if skipped_count:
            first_messages = " ".join(
                error_messages[:3]
            )

            messages.warning(
                request,
                (
                    f"{skipped_count} pupil(s) "
                    f"were not saved. "
                    f"{first_messages}"
                ),
            )

        return redirect(
            f"{request.path}"
            f"?class_id={selected_class.id}"
        )

    existing_mark_map = {
        (
            mark.student_id,
            mark.paper_id,
        ): mark
        for mark in StudentPaperMark.objects.filter(
            student__in=students,
            paper__in=papers,
        )
    }

    existing_result_map = {
        result.student_id: result
        for result in StudentResult.objects.filter(
            student__in=students,
            exam=exam,
            subject=subject,
        )
    }

    rows = []

    for student in students:
        mark_cells = []

        for paper in papers:
            existing_mark = (
                existing_mark_map.get(
                    (
                        student.id,
                        paper.id,
                    )
                )
            )

            mark_cells.append(
                {
                    "paper": paper,
                    "raw_score": (
                        existing_mark.raw_score
                        if existing_mark
                        else None
                    ),
                }
            )

        calculated = (
            calculate_existing_subject_score(
                student=student,
                exam=exam,
                subject=subject,
            )
        )

        rows.append(
            {
                "student": student,
                "mark_cells": mark_cells,
                "calculated": calculated,
                "result": existing_result_map.get(
                    student.id
                ),
            }
        )

    maximum_total = sum(
        (
            Decimal(paper.max_marks)
            for paper in papers
        ),
        start=Decimal("0.00"),
    )

    context = {
        "exam": exam,
        "subject": subject,
        "selected_class": selected_class,
        "papers": papers,
        "rows": rows,
        "maximum_total": maximum_total,
        "tenant_schema": get_schema_name(
            request,
            tenant_schema,
        ),
        "tenant_base_url": get_tenant_base_url(
            request,
            tenant_schema,
        ),
    }

    return render(
        request,
        "exampapers/enter_paper_marks.html",
        context,
    )


def build_enter_results_view(
    original_view,
):
    """
    Wrap the current ShuleHub enter_results_form.

    Subjects without configured papers continue using the
    original score entry.

    Subjects with configured papers are redirected to the
    paper-level entry page.
    """

    @tenant_and_role_required(
        RESULT_ENTRY_ROLES
    )
    @wraps(original_view)
    def wrapped_view(
        request,
        tenant_schema=None,
        *args,
        **kwargs,
    ):
        exam_id = (
            request.GET.get(
                "exam"
            )
            or request.POST.get(
                "exam"
            )
            or request.POST.get(
                "exam_id"
            )
        )

        subject_id = (
            request.GET.get(
                "subject"
            )
            or request.POST.get(
                "subject"
            )
            or request.POST.get(
                "subject_id"
            )
        )

        class_id = (
            request.GET.get(
                "class_id"
            )
            or request.POST.get(
                "class_id"
            )
        )

        if exam_id and subject_id:
            try:
                has_papers = (
                    ExamSubjectPaper.objects.filter(
                        component__exam_id=exam_id,
                        component__subject_id=subject_id,
                    ).exists()
                )
            except (
                TypeError,
                ValueError,
            ):
                has_papers = False

            if has_papers:
                if not class_id:
                    class_id = (
                        Exam.objects
                        .filter(pk=exam_id)
                        .values_list(
                            "student_class_id",
                            flat=True,
                        )
                        .first()
                    )

                destination = (
                    f"{get_tenant_base_url(request, tenant_schema)}"
                    f"/exam-papers/results/"
                    f"{exam_id}/{subject_id}/"
                )

                if class_id:
                    destination += (
                        f"?class_id={class_id}"
                    )

                return redirect(
                    destination
                )

        return original_view(
            request,
            tenant_schema=tenant_schema,
            *args,
            **kwargs,
        )

    return wrapped_view
