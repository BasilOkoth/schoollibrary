from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render

from digitallibrary.decorators import tenant_and_role_required
from digitallibrary.models import Class, ClassStream, Exam, StudentResult, Subject
from digitallibrary.result_grading import (
    build_student_result_defaults,
    get_result_grade_display,
)

from .access import (
    allowed_streams_for_user,
    can_manage_all_results,
    eligible_students,
    teacher_has_scope_access,
)
from .forms import TeachingAssignmentForm
from .models import TeachingAssignment

RESULT_ENTRY_ROLES = [
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
    "teacher",
    "class_teacher",
]

RESULT_MANAGER_ROLES = [
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
]

TWO_PLACES = Decimal("0.01")


def get_schema_name(request, tenant_schema=None):
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        parts = request.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "tenant":
            schema_name = parts[1]

    return schema_name


def tenant_base_url(request, tenant_schema=None):
    schema_name = get_schema_name(request, tenant_schema)
    if not schema_name or schema_name == "public":
        return ""
    return f"/tenant/{schema_name}/app"


def assignment_url(request, tenant_schema=None):
    return f"{tenant_base_url(request, tenant_schema)}/result-streams/assignments/"


@tenant_and_role_required(RESULT_MANAGER_ROLES)
def teaching_assignments(request, tenant_schema=None):
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.created_by = request.user

            try:
                assignment.save()
            except Exception as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Teacher assignment saved successfully.")
                return redirect(assignment_url(request, tenant_schema))
    else:
        form = TeachingAssignmentForm()

    assignments = TeachingAssignment.objects.select_related(
        "teacher",
        "subject",
        "school_class",
        "stream",
    )

    return render(
        request,
        "resultstreams/assignments.html",
        {
            "form": form,
            "assignments": assignments,
            "tenant_base_url": tenant_base_url(request, tenant_schema),
        },
    )


@tenant_and_role_required(RESULT_MANAGER_ROLES)
def delete_teaching_assignment(request, assignment_id, tenant_schema=None):
    assignment = get_object_or_404(TeachingAssignment, pk=assignment_id)

    if request.method == "POST":
        assignment.delete()
        messages.success(request, "Teacher assignment deleted.")

    return redirect(assignment_url(request, tenant_schema))


def decimal_mark(value, label):
    try:
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"Enter a valid {label}.") from error


def exam_maximum(exam):
    try:
        maximum = Decimal(str(getattr(exam, "max_score", 100) or 100))
    except (InvalidOperation, TypeError, ValueError):
        maximum = Decimal("100")

    return maximum if maximum > 0 else Decimal("100")


def normalize_score(raw_score, maximum):
    return (raw_score / maximum * Decimal("100")).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def raw_from_percentage(percentage, maximum):
    return (Decimal(percentage) / Decimal("100") * maximum).quantize(
        TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )


def get_papers(
    exam,
    subject,
):
    """
    Return configured papers through their weighted component.

    ExamSubjectPaper no longer stores exam and subject directly.
    Those relationships are now held by ExamSubjectComponent.
    """

    try:
        from exampapers.models import (
            ExamSubjectPaper,
        )
    except (
        ImportError,
        LookupError,
    ):
        return []

    return list(
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


def secure_entry_url(
    request,
    exam,
    subject,
    school_class,
    tenant_schema=None,
    stream=None,
):
    url = (
        f"{tenant_base_url(request, tenant_schema)}"
        f"/result-streams/entry/{exam.id}/{subject.id}/{school_class.id}/"
    )
    if stream is not None:
        url += f"?stream_id={stream.id}"
    return url


def get_stream_scope(request, exam, school_class, subject):
    all_streams = ClassStream.objects.filter(
        school_class=school_class,
        is_active=True,
    ).order_by("name")

    class_has_streams = all_streams.exists()

    if not class_has_streams:
        access_allowed = teacher_has_scope_access(
            user=request.user,
            exam=exam,
            school_class=school_class,
            subject=subject,
        )
        return all_streams, all_streams, None, False, access_allowed, None

    allowed_streams = allowed_streams_for_user(
        user=request.user,
        exam=exam,
        school_class=school_class,
        subject=subject,
    )

    stream_id = request.GET.get("stream_id") or request.POST.get("stream_id")
    selected_stream = None
    stream_error = None

    if stream_id:
        try:
            selected_stream = allowed_streams.get(pk=stream_id)
        except (ClassStream.DoesNotExist, TypeError, ValueError):
            stream_error = "You are not assigned to enter results for that stream."
    elif allowed_streams.count() == 1:
        selected_stream = allowed_streams.first()

    return (
        all_streams,
        allowed_streams,
        selected_stream,
        True,
        allowed_streams.exists(),
        stream_error,
    )


def save_simple_results(
    request,
    exam,
    subject,
    school_class,
    selected_stream,
    tenant_schema,
):
    students = list(
        eligible_students(
            school_class=school_class,
            subject=subject,
            stream=selected_stream,
        )
    )

    maximum = exam_maximum(exam)

    if request.method == "POST":
        saved = 0
        errors = []

        with transaction.atomic():
            for student in students:
                raw_text = (request.POST.get(f"score_{student.id}", "") or "").strip()

                if raw_text == "":
                    continue

                try:
                    raw_score = decimal_mark(
                        raw_text,
                        f"score for {student.get_full_name()}",
                    )
                except ValueError as error:
                    errors.append(str(error))
                    continue

                if raw_score < 0 or raw_score > maximum:
                    errors.append(
                        f"{student.get_full_name()}: score must be between 0 and {maximum}."
                    )
                    continue

                percentage = normalize_score(raw_score, maximum)

                result_defaults = build_student_result_defaults(
                    score=percentage,
                    percentage_score=percentage,
                    school_class=school_class,
                    exam=exam,
                    subject=subject,
                    user=request.user,
                    extra_remarks=(
                        f"Raw result: {raw_score}/{maximum}"
                    ),
                )

                StudentResult.objects.update_or_create(
                    student=student,
                    exam=exam,
                    subject=subject,
                    defaults=result_defaults,
                )
                saved += 1

        if saved:
            messages.success(request, f"Results saved for {saved} student(s).")
        if errors:
            messages.warning(request, " ".join(errors[:5]))

        return redirect(
            secure_entry_url(
                request,
                exam,
                subject,
                school_class,
                tenant_schema,
                selected_stream,
            )
        )

    existing_results = {
        result.student_id: result
        for result in StudentResult.objects.filter(
            student__in=students,
            exam=exam,
            subject=subject,
        )
    }

    rows = []
    for student in students:
        result = existing_results.get(student.id)
        rows.append(
            {
                "student": student,
                "result": result,
                "grade_display": get_result_grade_display(
                    result
                ),
                "raw_score": (
                    raw_from_percentage(result.score, maximum)
                    if result is not None
                    else None
                ),
            }
        )

    return render(
        request,
        "resultstreams/entry.html",
        {
            "exam": exam,
            "subject": subject,
            "selected_class": school_class,
            "selected_stream": selected_stream,
            "rows": rows,
            "maximum": maximum,
            "tenant_base_url": tenant_base_url(request, tenant_schema),
        },
    )


def save_paper_results(
    request,
    exam,
    subject,
    school_class,
    selected_stream,
    papers,
    tenant_schema,
):
    from exampapers.models import StudentPaperMark
    from exampapers.services import (
        PaperMarkError,
        calculate_existing_subject_score,
        save_student_paper_marks,
    )

    students = list(
        eligible_students(
            school_class=school_class,
            subject=subject,
            stream=selected_stream,
        )
    )

    if request.method == "POST":
        saved = 0
        errors = []

        for student in students:
            submitted = {
                paper.id: (
                    request.POST.get(f"mark_{student.id}_{paper.id}", "") or ""
                ).strip()
                for paper in papers
            }

            entered = [value for value in submitted.values() if value != ""]
            if not entered:
                continue

            if len(entered) != len(papers):
                errors.append(
                    f"{student.get_full_name()}: enter marks for every paper."
                )
                continue

            try:
                save_student_paper_marks(
                    student=student,
                    exam=exam,
                    subject=subject,
                    marks_by_paper_id=submitted,
                    entered_by=request.user,
                )
            except PaperMarkError as error:
                message = error.messages[0] if getattr(error, "messages", None) else str(error)
                errors.append(f"{student.get_full_name()}: {message}")
            except Exception as error:
                errors.append(f"{student.get_full_name()}: {error}")
            else:
                saved += 1

        if saved:
            messages.success(request, f"Paper marks saved for {saved} student(s).")
        if errors:
            messages.warning(request, " ".join(errors[:4]))

        return redirect(
            secure_entry_url(
                request,
                exam,
                subject,
                school_class,
                tenant_schema,
                selected_stream,
            )
        )

    existing_marks = {
        (mark.student_id, mark.paper_id): mark
        for mark in StudentPaperMark.objects.filter(
            student__in=students,
            paper__in=papers,
        )
    }

    existing_results = {
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
            mark = existing_marks.get((student.id, paper.id))
            mark_cells.append(
                {
                    "paper": paper,
                    "raw_score": mark.raw_score if mark else None,
                }
            )

        rows.append(
            {
                "student": student,
                "mark_cells": mark_cells,
                "grade_display": get_result_grade_display(
                    existing_results.get(student.id)
                ),
                "calculated": calculate_existing_subject_score(
                    student=student,
                    exam=exam,
                    subject=subject,
                ),
                "result": existing_results.get(student.id),
            }
        )

    maximum_total = sum(
        (Decimal(paper.max_marks) for paper in papers),
        start=Decimal("0.00"),
    )

    return render(
        request,
        "resultstreams/paper_entry.html",
        {
            "exam": exam,
            "subject": subject,
            "selected_class": school_class,
            "selected_stream": selected_stream,
            "papers": papers,
            "rows": rows,
            "maximum_total": maximum_total,
            "tenant_base_url": tenant_base_url(request, tenant_schema),
        },
    )


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def result_stream_entry(
    request,
    exam_id,
    subject_id,
    class_id,
    tenant_schema=None,
):
    exam = get_object_or_404(
        Exam.objects.select_related("student_class"),
        pk=exam_id,
    )
    subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
    school_class = get_object_or_404(Class, pk=class_id)

    if exam.student_class_id and exam.student_class_id != school_class.id:
        messages.error(request, "This exam belongs to a different class.")
        return redirect(
            f"{tenant_base_url(request, tenant_schema)}"
            f"/enter-results-form/?exam={exam.id}"
        )

    (
        all_streams,
        allowed_streams,
        selected_stream,
        class_has_streams,
        has_access,
        stream_error,
    ) = get_stream_scope(request, exam, school_class, subject)

    if can_manage_all_results(request.user):
        has_access = True

    if stream_error:
        messages.error(request, stream_error)

    papers = get_papers(exam, subject)

    if not has_access or (class_has_streams and selected_stream is None):
        return render(
            request,
            "resultstreams/stream_choice.html",
            {
                "exam": exam,
                "subject": subject,
                "selected_class": school_class,
                "all_streams": all_streams,
                "allowed_streams": allowed_streams,
                "has_access": has_access,
                "class_has_streams": class_has_streams,
                "has_papers": bool(papers),
                "tenant_base_url": tenant_base_url(request, tenant_schema),
            },
        )

    if papers:
        return save_paper_results(
            request,
            exam,
            subject,
            school_class,
            selected_stream,
            papers,
            tenant_schema,
        )

    return save_simple_results(
        request,
        exam,
        subject,
        school_class,
        selected_stream,
        tenant_schema,
    )


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def paper_result_bridge(request, exam_id, subject_id, tenant_schema=None):
    exam = get_object_or_404(Exam, pk=exam_id)
    class_id = (
        request.GET.get("class_id")
        or request.POST.get("class_id")
        or exam.student_class_id
    )

    if not class_id:
        messages.error(request, "Select a class before entering results.")
        return redirect(
            f"{tenant_base_url(request, tenant_schema)}"
            f"/enter-results-form/?exam={exam.id}&subject={subject_id}"
        )

    destination = (
        f"{tenant_base_url(request, tenant_schema)}"
        f"/result-streams/entry/{exam_id}/{subject_id}/{class_id}/"
    )

    stream_id = request.GET.get("stream_id") or request.POST.get("stream_id")
    if stream_id:
        destination += f"?stream_id={stream_id}"

    return redirect(destination)


def build_stream_aware_enter_results_view(original_view):
    @wraps(original_view)
    def wrapped_view(request, tenant_schema=None, *args, **kwargs):
        exam_id = (
            request.GET.get("exam")
            or request.GET.get("exam_id")
            or request.POST.get("exam")
            or request.POST.get("exam_id")
        )
        subject_id = (
            request.GET.get("subject")
            or request.GET.get("subject_id")
            or request.POST.get("subject")
            or request.POST.get("subject_id")
        )
        class_id = (
            request.GET.get("class_id")
            or request.GET.get("class")
            or request.POST.get("class_id")
            or request.POST.get("class")
        )

        if exam_id and subject_id:
            if not class_id:
                try:
                    class_id = Exam.objects.filter(pk=exam_id).values_list(
                        "student_class_id",
                        flat=True,
                    ).first()
                except (TypeError, ValueError):
                    class_id = None

            if class_id:
                destination = (
                    f"{tenant_base_url(request, tenant_schema)}"
                    f"/result-streams/entry/{exam_id}/{subject_id}/{class_id}/"
                )

                stream_id = request.GET.get("stream_id") or request.POST.get("stream_id")
                if stream_id:
                    destination += f"?stream_id={stream_id}"

                return redirect(destination)

        return original_view(
            request,
            tenant_schema=tenant_schema,
            *args,
            **kwargs,
        )

    return wrapped_view
