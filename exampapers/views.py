from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.db import connection
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


def configure_papers(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
):
    """
    Backward-compatible bridge to the weighted assessment
    component configuration page.

    Existing URLs that still point to views.configure_papers
    will continue to work. The actual configuration logic now
    lives in exampapers.component_views.configure_components.
    """

    from .component_views import configure_components

    return configure_components(
        request=request,
        exam_id=exam_id,
        subject_id=subject_id,
        tenant_schema=tenant_schema,
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
                f"No weighted assessment components have been configured "
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
