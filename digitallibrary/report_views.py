# digitallibrary/report_views.py
"""Tenant-safe report-card HTML and PDF views."""

from __future__ import annotations

import io

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django_tenants.utils import schema_context
from xhtml2pdf import pisa

from .decorators import tenant_and_role_required
from .models import (
    ClassTeacherAssignment,
    Exam,
    Student,
    StudentResult,
    TeacherSubject,
)
from .reporting import build_report_context, resolve_report_identity


REPORT_VIEW_ROLES = [
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
    "teacher",
    "class_teacher",
    "parent",
]


REPORT_MANAGER_ROLES = {
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
}


def resolve_tenant_schema(request, explicit_schema=None) -> str:
    """Resolve a non-public schema without guessing a school."""

    schema_name = (
        explicit_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        parts = request.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "tenant":
            schema_name = parts[1]

    if not schema_name or schema_name == "public":
        raise Http404("School tenant context was not detected.")

    return str(schema_name).strip()


def _tenant_url(request, schema_name: str, path: str) -> str:
    path = "/" + path.lstrip("/")

    if request.path.startswith("/tenant/"):
        return f"/tenant/{schema_name}/app{path}"

    return f"/app{path}"


def _user_role(user) -> str:
    profile = getattr(user, "profile", None)
    return str(getattr(profile, "role", "") or "").strip()


def _is_assigned_class_teacher(user, student_class, stream) -> bool:
    if not student_class:
        return False

    if getattr(student_class, "class_teacher_id", None) == user.id:
        return True

    stream_name = getattr(stream, "name", "") if stream else ""

    return ClassTeacherAssignment.objects.filter(
        class_obj=student_class,
        class_teacher=user,
        stream_name__iexact=stream_name,
    ).exists()


def _is_assigned_subject_teacher(user, student_class, exam) -> bool:
    if not student_class:
        return False

    return TeacherSubject.objects.filter(
        teacher=user,
        class_assigned=student_class,
        academic_year=str(exam.academic_year),
    ).exists()


def user_can_view_report(user, student, exam) -> bool:
    """Apply object-level authorization to a learner report."""

    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    role = _user_role(user)

    if role in REPORT_MANAGER_ROLES:
        return True

    identity = resolve_report_identity(student, exam)

    if role in {"teacher", "class_teacher"}:
        return (
            _is_assigned_class_teacher(
                user,
                identity.student_class,
                identity.stream,
            )
            or _is_assigned_subject_teacher(
                user,
                identity.student_class,
                exam,
            )
        )

    if role == "parent":
        profile = getattr(user, "profile", None)
        children = getattr(profile, "children", None)
        return bool(children and children.filter(pk=student.pk).exists())

    return False


def _report_back_url(request, schema_name: str, student_id: int) -> str:
    try:
        path = reverse(
            "digitallibrary:student_performance",
            kwargs={"student_id": student_id},
        )
    except NoReverseMatch:
        path = f"/performance/student/{student_id}/"

    if request.path.startswith("/tenant/") and not path.startswith("/tenant/"):
        normalized = path
        if normalized.startswith("/app/"):
            normalized = normalized[4:]
        return _tenant_url(request, schema_name, normalized)

    return path


def _select_exam(student, exam_id):
    if exam_id:
        return get_object_or_404(Exam, pk=exam_id)

    result_exam_ids = student.results.values_list("exam_id", flat=True)

    return (
        Exam.objects.filter(
            id__in=result_exam_ids,
            is_active=True,
        )
        .order_by("-academic_year", "-term", "-exam_date", "-id")
        .first()
    )


def _load_report_context(
    request,
    *,
    schema_name: str,
    student_id: int,
    exam_id=None,
) -> dict:
    student = get_object_or_404(Student, pk=student_id)
    selected_exam_id = (
        exam_id
        or request.GET.get("exam")
        or request.GET.get("exam_id")
    )
    exam = _select_exam(student, selected_exam_id)

    if exam is None:
        raise Http404("No examination results are available for this learner.")

    if not StudentResult.objects.filter(
        student=student,
        exam=exam,
        score__isnull=False,
    ).exists():
        raise Http404(
            "No valid subject results are available for this examination."
        )

    if not user_can_view_report(request.user, student, exam):
        raise PermissionDenied(
            "You do not have permission to view this learner's report."
        )

    context = build_report_context(student, exam)
    query = f"?exam_id={exam.id}"
    context.update(
        {
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_base_url": _tenant_url(request, schema_name, "/").rstrip("/"),
            "back_url": _report_back_url(
                request,
                schema_name,
                student.id,
            ),
            "download_pdf_url": (
                _tenant_url(
                    request,
                    schema_name,
                    f"/performance/report-card/{student.id}/pdf/",
                )
                + query
            ),
        }
    )

    return context


@tenant_and_role_required(REPORT_VIEW_ROLES)
def student_report_card(
    request,
    tenant_schema=None,
    student_id=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Render the canonical report card."""

    if student_id is None:
        raise Http404("Student ID is required.")

    schema_name = resolve_tenant_schema(request, tenant_schema)

    with schema_context(schema_name):
        try:
            context = _load_report_context(
                request,
                schema_name=schema_name,
                student_id=student_id,
                exam_id=exam_id,
            )
        except Http404 as exc:
            messages.warning(request, str(exc))
            return redirect(
                _report_back_url(
                    request,
                    schema_name,
                    student_id,
                )
            )

        return render(
            request,
            "performance/student_report_card.html",
            context,
        )


@tenant_and_role_required(REPORT_VIEW_ROLES)
def student_report_card_pdf(
    request,
    tenant_schema=None,
    student_id=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Generate a PDF from the same canonical report context."""

    if student_id is None:
        raise Http404("Student ID is required.")

    schema_name = resolve_tenant_schema(request, tenant_schema)

    with schema_context(schema_name):
        context = _load_report_context(
            request,
            schema_name=schema_name,
            student_id=student_id,
            exam_id=exam_id,
        )
        html = render_to_string(
            "performance/student_report_card_pdf.html",
            context,
            request=request,
        )

        output = io.BytesIO()
        status = pisa.CreatePDF(
            src=html,
            dest=output,
            encoding="UTF-8",
        )

        if status.err:
            return HttpResponse(
                "The report PDF could not be generated.",
                status=500,
                content_type="text/plain",
            )

        student = context["student"]
        exam = context["exam"]
        filename = (
            f"{student.admission_number}-{exam.academic_year}-"
            f"term-{exam.term}-report.pdf"
        )

        response = HttpResponse(
            output.getvalue(),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        return response
