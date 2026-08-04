# digitallibrary/result_entry_views.py
"""Canonical bulk result entry using the shared grading service."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pandas as pd

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import schema_context

from .decorators import tenant_and_role_required
from .models import (
    Class,
    Exam,
    Student,
    StudentResult,
    Subject,
)
from .report_views import resolve_tenant_schema
from .reporting import (
    percentage_for_score,
    registered_subjects_for_year,
)
from .result_grading import (
    build_student_result_defaults,
    get_model_field,
    get_result_grade_display,
    is_old_curriculum_class,
    model_has_field,
    resolve_grade,
)


RESULT_ENTRY_ROLES = [
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
    "teacher",
    "class_teacher",
]


def get_students_for_subject_results(
    student_class,
    subject,
    academic_year=None,
):
    """
    Return only learners registered for the selected subject.

    The function never falls back to every learner in the class. A learner who
    is not registered for the subject is omitted from result entry.
    """

    if not student_class or not subject:
        return Student.objects.none(), True

    students = Student.objects.filter(
        current_class=student_class,
        is_active=True,
    )

    if model_has_field(Student, "status"):
        students = students.filter(status="active")

    students = (
        students.select_related("current_class", "stream")
        .prefetch_related("subjects")
        .order_by(
            "admission_number",
            "last_name",
            "first_name",
        )
    )

    eligible_ids = []

    for student in students:
        registered_subjects, _ = registered_subjects_for_year(
            student=student,
            academic_year=academic_year,
            student_class=student_class,
        )

        if registered_subjects.filter(pk=subject.pk).exists():
            eligible_ids.append(student.id)

    return students.filter(pk__in=eligible_ids), True


def registered_subjects_for_class(
    students,
    *,
    student_class,
    academic_year,
):
    """Return subjects registered by at least one learner in the class."""

    subject_ids = set()

    for student in students:
        registered_subjects, _ = registered_subjects_for_year(
            student=student,
            academic_year=academic_year,
            student_class=student_class,
        )
        subject_ids.update(
            registered_subjects.values_list("id", flat=True)
        )

    return Subject.objects.filter(
        id__in=subject_ids,
        is_active=True,
    ).distinct().order_by(
        "result_code",
        "category",
        "order",
        "name",
    )


def _result_defaults(
    *,
    score: Decimal,
    student_class,
    exam,
    subject,
    user,
    teacher_comment: str,
) -> dict:
    percentage = percentage_for_score(score, exam.max_score)

    if percentage is None:
        raise ValueError("A valid maximum score is required.")

    resolution = resolve_grade(
        percentage_score=percentage,
        school_class=student_class,
        exam=exam,
        subject=subject,
    )
    defaults = build_student_result_defaults(
        score=score,
        percentage_score=percentage,
        school_class=student_class,
        exam=exam,
        subject=subject,
        user=user,
    )

    if model_has_field(StudentResult, "grade_label"):
        defaults["grade_label"] = resolution.label

    if model_has_field(StudentResult, "grading_system_used"):
        defaults["grading_system_used"] = resolution.system_code

    if model_has_field(StudentResult, "teacher_comment"):
        defaults["teacher_comment"] = teacher_comment.strip()

    grade_field = get_model_field(StudentResult, "grade")
    remote_field = getattr(grade_field, "remote_field", None)

    if remote_field and "grade" not in defaults:
        defaults["grade"] = None

    return defaults


def _tenant_base_url(request, schema_name: str) -> str:
    if request.path.startswith("/tenant/"):
        return f"/tenant/{schema_name}/app"
    return "/app"


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def bulk_results_entry(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Enter subject results with curriculum-aware grading."""

    schema_name = resolve_tenant_schema(request, tenant_schema)
    tenant_base_url = _tenant_base_url(request, schema_name)
    bulk_select_url = f"{tenant_base_url}/bulk-enter-results/"

    with schema_context(schema_name):
        exam = get_object_or_404(Exam, pk=exam_id)
        subject = get_object_or_404(Subject, pk=subject_id)

        class_id = (
            request.session.get("bulk_class_id")
            or request.GET.get("class_id")
        )

        if not class_id:
            messages.error(request, "Please select a class first.")
            return redirect(bulk_select_url)

        student_class = get_object_or_404(Class, pk=class_id)

        if exam.student_class_id and exam.student_class_id != student_class.id:
            messages.error(
                request,
                "The selected examination belongs to a different class.",
            )
            return redirect(bulk_select_url)

        if not subject.applicable_classes.filter(pk=student_class.pk).exists():
            messages.error(
                request,
                f"{subject.name} is not configured for {student_class.name}.",
            )
            return redirect(bulk_select_url)

        request.session["bulk_class_id"] = student_class.id
        students, using_subject_assignments = (
            get_students_for_subject_results(
                student_class=student_class,
                subject=subject,
                academic_year=exam.academic_year,
            )
        )

        existing_results = {
            result.student_id: result
            for result in StudentResult.objects.filter(
                exam=exam,
                subject=subject,
                student__in=students,
            ).select_related("student", "grade")
        }

        if request.method == "POST":
            saved_count = 0
            errors: list[str] = []
            student_map = {
                student.id: student
                for student in students
            }
            maximum = Decimal(str(exam.max_score or 100))

            with transaction.atomic():
                for student_id, student in student_map.items():
                    raw_score = request.POST.get(f"score_{student_id}", "")
                    raw_comment = request.POST.get(
                        f"comment_{student_id}",
                        "",
                    )

                    if not str(raw_score).strip():
                        continue

                    try:
                        score = Decimal(str(raw_score))
                    except (InvalidOperation, TypeError, ValueError):
                        errors.append(
                            f"{student.admission_number}: invalid score."
                        )
                        continue

                    if maximum <= 0:
                        errors.append("The examination maximum score is invalid.")
                        break

                    if score < 0 or score > maximum:
                        errors.append(
                            f"{student.admission_number}: score must be between "
                            f"0 and {maximum}."
                        )
                        continue

                    defaults = _result_defaults(
                        score=score,
                        student_class=student_class,
                        exam=exam,
                        subject=subject,
                        user=request.user,
                        teacher_comment=raw_comment,
                    )

                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults=defaults,
                    )
                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    f"Saved {saved_count} result(s) for {subject.name}.",
                )

            if errors:
                preview = " ".join(errors[:5])
                remaining = len(errors) - 5
                if remaining > 0:
                    preview += f" Plus {remaining} more error(s)."
                messages.warning(request, preview)

            if not saved_count and not errors:
                messages.info(request, "No scores were entered.")

            return redirect(
                f"{tenant_base_url}/bulk-results/{exam.id}/{subject.id}/"
                f"?class_id={student_class.id}"
            )

        existing_scores = {}
        existing_grades = {}
        existing_points = {}
        existing_comments = {}

        for student in students:
            result = existing_results.get(student.id)

            if result:
                existing_scores[student.id] = result.score
                existing_grades[student.id] = (
                    getattr(result, "grade_label", "")
                    or get_result_grade_display(result)
                    or "—"
                )
                existing_points[student.id] = result.points or "—"
                existing_comments[student.id] = (
                    getattr(result, "teacher_comment", "") or ""
                )
            else:
                existing_scores[student.id] = ""
                existing_grades[student.id] = "—"
                existing_points[student.id] = "—"
                existing_comments[student.id] = ""

        if using_subject_assignments and not students.exists():
            no_students_message = (
                f"No learners have been assigned to {subject.name} "
                f"for {student_class.name} in {exam.academic_year}."
            )
        elif not students.exists():
            no_students_message = (
                "No active eligible learners were found for this class."
            )
        else:
            no_students_message = ""

        context = {
            "exam": exam,
            "subject": subject,
            "class": student_class,
            "students": students,
            "existing_scores": existing_scores,
            "existing_grades": existing_grades,
            "existing_points": existing_points,
            "existing_comments": existing_comments,
            "student_count": students.count(),
            "use_cbe": not is_old_curriculum_class(student_class),
            "using_subject_assignments": using_subject_assignments,
            "no_students_message": no_students_message,
            "max_score": exam.max_score or 100,
            "title": (
                f"Enter Results - {exam.name} - "
                f"{subject.name} - {student_class.name}"
            ),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
            "tenant_bulk_select_url": bulk_select_url,
            "tenant_student_subjects_url": (
                f"{tenant_base_url}/student-subjects/"
            ),
        }

        return render(
            request,
            "digitallibrary/bulk_results_entry.html",
            context,
        )


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def exam_results_entry(
    request,
    exam_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Enter one subject's results for the examination cohort."""

    schema_name = resolve_tenant_schema(request, tenant_schema)
    tenant_base_url = _tenant_base_url(request, schema_name)

    with schema_context(schema_name):
        exam = get_object_or_404(Exam, pk=exam_id)
        student_class = exam.student_class

        class_students = Student.objects.filter(
            current_class=student_class,
            is_active=True,
        ) if student_class else Student.objects.none()

        if model_has_field(Student, "status"):
            class_students = class_students.filter(status="active")

        subjects = registered_subjects_for_class(
            class_students,
            student_class=student_class,
            academic_year=exam.academic_year,
        ) if student_class else Subject.objects.none()
        subject_id = (
            request.POST.get("subject_id")
            or request.GET.get("subject")
            or request.GET.get("subject_id")
        )
        selected_subject = (
            get_object_or_404(
                subjects,
                pk=subject_id,
            )
            if subject_id
            else None
        )
        students = Student.objects.none()
        existing_results = {}

        if selected_subject and student_class:
            students, _ = get_students_for_subject_results(
                student_class=student_class,
                subject=selected_subject,
                academic_year=exam.academic_year,
            )
            existing_results = {
                result.student_id: result
                for result in StudentResult.objects.filter(
                    exam=exam,
                    subject=selected_subject,
                    student__in=students,
                ).select_related("grade")
            }

        if request.method == "POST":
            if selected_subject is None or student_class is None:
                messages.error(
                    request,
                    "Select an examination with a class and a valid subject.",
                )
                return redirect(
                    f"{tenant_base_url}/exams/{exam.id}/results/"
                )

            saved_count = 0
            errors = []
            maximum = Decimal(str(exam.max_score or 100))

            with transaction.atomic():
                for student in students:
                    raw_score = request.POST.get(f"score_{student.id}", "")

                    if not str(raw_score).strip():
                        continue

                    try:
                        score = Decimal(str(raw_score))
                    except (InvalidOperation, TypeError, ValueError):
                        errors.append(
                            f"{student.admission_number}: invalid score."
                        )
                        continue

                    if score < 0 or score > maximum:
                        errors.append(
                            f"{student.admission_number}: score must be between "
                            f"0 and {maximum}."
                        )
                        continue

                    defaults = _result_defaults(
                        score=score,
                        student_class=student_class,
                        exam=exam,
                        subject=selected_subject,
                        user=request.user,
                        teacher_comment=request.POST.get(
                            f"comment_{student.id}",
                            "",
                        ),
                    )
                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=selected_subject,
                        defaults=defaults,
                    )
                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    f"Saved {saved_count} result(s) for "
                    f"{selected_subject.name}.",
                )

            if errors:
                messages.warning(request, " ".join(errors[:5]))

            return redirect(
                f"{tenant_base_url}/exams/{exam.id}/results/"
                f"?subject={selected_subject.id}"
            )

        context = {
            "exam": exam,
            "subjects": subjects,
            "selected_subject": selected_subject,
            "students": students,
            "existing_results": existing_results,
            "title": f"Enter Results - {exam.name}",
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
        }

        return render(
            request,
            "performance/exam_results_entry.html",
            context,
        )


def _student_can_take_subject(
    student,
    subject,
    *,
    academic_year,
    student_class=None,
) -> bool:
    """Return True only when the learner has a subject registration."""

    registered_subjects, _ = registered_subjects_for_year(
        student=student,
        academic_year=academic_year,
        student_class=student_class or student.current_class,
    )
    return registered_subjects.filter(pk=subject.pk).exists()


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def bulk_results_entry_by_class(
    request,
    exam_id,
    class_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Enter a class result matrix while validating subject eligibility."""

    schema_name = resolve_tenant_schema(request, tenant_schema)
    tenant_base_url = _tenant_base_url(request, schema_name)

    with schema_context(schema_name):
        exam = get_object_or_404(Exam, pk=exam_id)
        student_class = get_object_or_404(Class, pk=class_id)

        if exam.student_class_id and exam.student_class_id != student_class.id:
            messages.error(
                request,
                "The selected examination belongs to a different class.",
            )
            return redirect(f"{tenant_base_url}/exams/")

        students = Student.objects.filter(
            current_class=student_class,
            is_active=True,
        )

        if model_has_field(Student, "status"):
            students = students.filter(status="active")

        students = students.order_by(
            "admission_number",
            "last_name",
            "first_name",
        )
        subjects = registered_subjects_for_class(
            students,
            student_class=student_class,
            academic_year=exam.academic_year,
        )
        existing_results = {
            f"{result.student_id}_{result.subject_id}": result
            for result in StudentResult.objects.filter(
                exam=exam,
                student__in=students,
                subject__in=subjects,
            ).select_related("grade")
        }

        if request.method == "POST":
            valid_students = {
                student.id: student
                for student in students
            }
            valid_subjects = {
                subject.id: subject
                for subject in subjects
            }
            maximum = Decimal(str(exam.max_score or 100))
            saved_count = 0
            errors = []

            with transaction.atomic():
                for key, raw_score in request.POST.items():
                    if (
                        not key.startswith("score_")
                        or not str(raw_score).strip()
                    ):
                        continue

                    identifiers = key.removeprefix("score_").split("_")

                    if len(identifiers) != 2:
                        continue

                    try:
                        student_id, subject_id = map(int, identifiers)
                        score = Decimal(str(raw_score))
                    except (InvalidOperation, TypeError, ValueError):
                        errors.append(f"Invalid result field: {key}.")
                        continue

                    student = valid_students.get(student_id)
                    subject = valid_subjects.get(subject_id)

                    if student is None or subject is None:
                        errors.append(f"Invalid learner or subject in {key}.")
                        continue

                    if not _student_can_take_subject(
                        student,
                        subject,
                        academic_year=exam.academic_year,
                        student_class=student_class,
                    ):
                        errors.append(
                            f"{student.admission_number} is not assigned to "
                            f"{subject.name}."
                        )
                        continue

                    if score < 0 or score > maximum:
                        errors.append(
                            f"{student.admission_number}/{subject.name}: "
                            f"score must be between 0 and {maximum}."
                        )
                        continue

                    defaults = _result_defaults(
                        score=score,
                        student_class=student_class,
                        exam=exam,
                        subject=subject,
                        user=request.user,
                        teacher_comment=request.POST.get(
                            f"comment_{student.id}_{subject.id}",
                            "",
                        ),
                    )
                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults=defaults,
                    )
                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    f"Saved {saved_count} result(s) for "
                    f"{student_class.name}.",
                )

            if errors:
                messages.warning(request, " ".join(errors[:5]))

            return redirect(
                f"{tenant_base_url}/bulk-results/class/"
                f"{exam.id}/{student_class.id}/"
            )

        context = {
            "exam": exam,
            "class": student_class,
            "students": students,
            "subjects": subjects,
            "existing_results": existing_results,
            "student_count": students.count(),
            "subject_count": subjects.count(),
            "title": f"Bulk Results - {exam.name} - {student_class.name}",
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
        }

        return render(
            request,
            "performance/bulk_results_entry_by_class.html",
            context,
        )


def _normalized_upload_rows(uploaded_file):
    extension = uploaded_file.name.rsplit(".", 1)[-1].lower()

    if extension == "csv":
        dataframe = pd.read_csv(
            uploaded_file,
            dtype={"Admission Number": str},
        )
    elif extension in {"xls", "xlsx"}:
        dataframe = pd.read_excel(
            uploaded_file,
            dtype=str,
        )
    else:
        raise ValueError("Upload a CSV, XLS or XLSX file.")

    dataframe.columns = [
        str(column).strip().lower()
        for column in dataframe.columns
    ]
    admission_column = next(
        (
            column
            for column in dataframe.columns
            if any(
                token in column
                for token in ("admission", "adm", "registration", "reg")
            )
        ),
        None,
    )
    score_column = next(
        (
            column
            for column in dataframe.columns
            if any(
                token in column
                for token in ("score", "mark", "result")
            )
        ),
        None,
    )

    if admission_column is None or score_column is None:
        raise ValueError(
            'The file must contain "Admission Number" and "Score" columns.'
        )

    for index, row in dataframe.iterrows():
        admission = row.get(admission_column)
        score = row.get(score_column)

        if pd.isna(admission) or pd.isna(score):
            continue

        admission_number = str(admission).strip()

        if admission_number.endswith(".0"):
            admission_number = admission_number[:-2]

        yield index + 2, admission_number, score


@tenant_and_role_required(RESULT_ENTRY_ROLES)
def bulk_upload_results(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Upload CSV or Excel marks and grade each result automatically."""

    schema_name = resolve_tenant_schema(request, tenant_schema)
    tenant_base_url = _tenant_base_url(request, schema_name)
    upload_url = f"{tenant_base_url}/bulk-enter-results/"
    exam_list_url = f"{tenant_base_url}/exams/"

    with schema_context(schema_name):
        exams = Exam.objects.filter(is_active=True).order_by(
            "-academic_year",
            "-created_at",
        )
        subjects = Subject.objects.filter(is_active=True).order_by(
            "result_code",
            "name",
        )

        if request.method == "POST":
            exam_id = request.POST.get("exam")
            subject_id = request.POST.get("subject")
            uploaded_file = request.FILES.get("excel_file")

            if not exam_id or not subject_id or uploaded_file is None:
                messages.error(
                    request,
                    "Select an examination, subject and CSV or Excel file.",
                )
                return redirect(upload_url)

            exam = get_object_or_404(Exam, pk=exam_id)
            subject = get_object_or_404(
                Subject,
                pk=subject_id,
                is_active=True,
            )

            if (
                exam.student_class_id
                and not subject.applicable_classes.filter(
                    pk=exam.student_class_id,
                ).exists()
            ):
                messages.error(
                    request,
                    f"{subject.name} is not configured for "
                    f"{exam.student_class.name}.",
                )
                return redirect(upload_url)

            eligible_students = None

            if exam.student_class:
                eligible_students, _ = get_students_for_subject_results(
                    student_class=exam.student_class,
                    subject=subject,
                    academic_year=exam.academic_year,
                )

            maximum = Decimal(str(exam.max_score or 100))
            processed = 0
            errors = []

            try:
                rows = list(_normalized_upload_rows(uploaded_file))
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect(upload_url)

            with transaction.atomic():
                for row_number, admission_number, raw_score in rows:
                    student_query = Student.objects.filter(
                        admission_number=admission_number,
                        is_active=True,
                    )

                    if eligible_students is not None:
                        student_query = student_query.filter(
                            pk__in=eligible_students.values("pk")
                        )

                    student = student_query.first()

                    if student is None:
                        errors.append(
                            f"Row {row_number}: learner "
                            f"{admission_number} is missing or not eligible."
                        )
                        continue

                    try:
                        score = Decimal(str(raw_score))
                    except (InvalidOperation, TypeError, ValueError):
                        errors.append(
                            f"Row {row_number}: invalid score {raw_score}."
                        )
                        continue

                    if score < 0 or score > maximum:
                        errors.append(
                            f"Row {row_number}: score must be between "
                            f"0 and {maximum}."
                        )
                        continue

                    student_class = (
                        exam.student_class
                        or student.current_class
                    )

                    if not _student_can_take_subject(
                        student,
                        subject,
                        academic_year=exam.academic_year,
                        student_class=student_class,
                    ):
                        errors.append(
                            f"Row {row_number}: learner "
                            f"{admission_number} is not assigned to "
                            f"{subject.name}."
                        )
                        continue

                    defaults = _result_defaults(
                        score=score,
                        student_class=student_class,
                        exam=exam,
                        subject=subject,
                        user=request.user,
                        teacher_comment="",
                    )
                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults=defaults,
                    )
                    processed += 1

            if processed:
                messages.success(
                    request,
                    f"Processed {processed} result(s) for "
                    f"{exam.name} - {subject.name}.",
                )

            for error in errors[:5]:
                messages.warning(request, error)

            if len(errors) > 5:
                messages.warning(
                    request,
                    f"...and {len(errors) - 5} more error(s).",
                )

            return redirect(exam_list_url)

        context = {
            "exams": exams,
            "subjects": subjects,
            "title": "Bulk Result Upload",
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_exam_list_url": exam_list_url,
            "tenant_bulk_enter_url": upload_url,
            "tenant_upload_url": upload_url,
        }

        return render(
            request,
            "performance/bulk_excel_upload.html",
            context,
        )
