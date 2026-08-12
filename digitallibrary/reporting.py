# digitallibrary/reporting.py
"""Canonical report-card calculations shared by HTML and PDF views."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import (
    ClassTeacherAssignment,
    Exam,
    SchoolSetting,
    Student,
    StudentEnrollment,
    StudentEnrollmentSubject,
    StudentResult,
    StudentSubject,
    Subject,
    UserProfile,
)
from .result_grading import GradeResolution, resolve_grade


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ReportResultRow:
    """One subject prepared for report presentation."""

    result_id: int | None
    subject: Subject
    score: Decimal | None
    max_score: Decimal
    percentage: Decimal | None
    grade: str
    points: Decimal | None
    progress: str
    performance_band: str
    subject_position: int | None
    subject_size: int
    teacher_comment: str
    status: str
    is_entered: bool


@dataclass(frozen=True)
class ReportIdentity:
    """Historical class and stream attached to the selected examination."""

    student_class: object | None
    stream: object | None
    enrollment: StudentEnrollment | None


@dataclass(frozen=True)
class Ranking:
    """Competition ranking where ties share a position."""

    position: int | None
    size: int


def decimal_value(value, default: str = "0") -> Decimal:
    """Convert an arbitrary value to Decimal without propagating bad input."""

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def percentage_for_score(score, max_score) -> Decimal | None:
    """Return a normalized percentage, or None when the score is missing."""

    if score in (None, ""):
        return None

    score_value = decimal_value(score)
    maximum_value = decimal_value(max_score, "100")

    if maximum_value <= ZERO:
        return None

    percentage = (score_value / maximum_value) * HUNDRED
    return min(max(percentage, ZERO), HUNDRED).quantize(Decimal("0.1"))


def progress_for_resolution(resolution: GradeResolution) -> tuple[str, str]:
    """Map a resolved grade to a stable progress label and presentation band."""

    label = str(resolution.label or "").strip().upper()

    if resolution.system_code == "cbe":
        if label in {"EE1", "EE2"}:
            return "Exceeding Expectations", "excellent"
        if label in {"ME1", "ME2"}:
            return "Meeting Expectations", "good"
        if label in {"AE1", "AE2"}:
            return "Approaching Expectations", "support"
        return "Below Expectations", "critical"

    if label in {"A", "A-"}:
        return "Excellent", "excellent"
    if label in {"B+", "B", "B-"}:
        return "Very Good", "good"
    if label in {"C+", "C", "C-"}:
        return "Satisfactory", "satisfactory"
    if label in {"D+", "D", "D-"}:
        return "Needs Support", "support"
    return "Critical", "critical"


def subject_comment(
    subject_name: str,
    progress: str,
    *,
    partial_report: bool = False,
) -> str:
    """Generate a factual subject remark from the resolved performance."""

    comments = {
        "Exceeding Expectations": (
            f"Excellent mastery of {subject_name}. Maintain this standard "
            "through consistent practice and deeper application."
        ),
        "Excellent": (
            f"Excellent performance in {subject_name}. Maintain the strong "
            "study habits and consistent practice."
        ),
        "Meeting Expectations": (
            f"The learner is meeting expectations in {subject_name}. Continued "
            "practice will strengthen accuracy and confidence."
        ),
        "Very Good": (
            f"Very good performance in {subject_name}. Focused revision can "
            "raise the score further."
        ),
        "Satisfactory": (
            f"Satisfactory performance in {subject_name}. Regular revision and "
            "practice are needed to improve weaker areas."
        ),
        "Approaching Expectations": (
            f"The learner is approaching expectations in {subject_name}. "
            "Additional guided practice and teacher support are required."
        ),
        "Needs Support": (
            f"Performance in {subject_name} is below the expected standard. "
            "More revision, practice and teacher support are required."
        ),
        "Below Expectations": (
            f"Performance in {subject_name} is below expectations. Immediate "
            "remedial support, regular practice and close follow-up are needed."
        ),
        "Critical": (
            f"Performance in {subject_name} is critically below the expected "
            "standard. Urgent improvement is required through regular revision, "
            "additional practice and teacher support."
        ),
    }

    comment = comments.get(
        progress,
        f"Performance in {subject_name} has been recorded. Continued practice "
        "and teacher guidance are recommended.",
    )

    if partial_report:
        return f"{comment} This remark is based on the recorded result only."

    return comment


def overall_comments(
    learner_name: str,
    progress: str,
    *,
    is_complete: bool,
    recorded_subjects: int,
    expected_subjects: int,
) -> tuple[str, str]:
    """Generate class-teacher and principal remarks without claiming approval."""

    scope = ""
    if not is_complete:
        scope = (
            f"This report currently contains {recorded_subjects} of "
            f"{expected_subjects or recorded_subjects} expected subject results. "
        )

    class_comments = {
        "Exceeding Expectations": (
            f"{learner_name} has demonstrated excellent academic performance. "
            "The learner should maintain the same discipline and consistency."
        ),
        "Excellent": (
            f"{learner_name} has demonstrated excellent academic performance. "
            "The learner should maintain the same discipline and consistency."
        ),
        "Meeting Expectations": (
            f"{learner_name} is meeting the expected learning outcomes. "
            "Continued focused revision will support further growth."
        ),
        "Very Good": (
            f"{learner_name} has demonstrated very good performance. Continued "
            "focused revision can lead to even stronger results."
        ),
        "Satisfactory": (
            f"{learner_name} has made satisfactory progress but still has room "
            "for improvement. Regular revision and practice are recommended."
        ),
        "Approaching Expectations": (
            f"{learner_name} is approaching the expected learning outcomes and "
            "requires additional guided practice and close teacher support."
        ),
        "Needs Support": (
            f"{learner_name}'s performance is below the expected standard and "
            "requires additional support, regular revision and follow-up."
        ),
        "Below Expectations": (
            f"{learner_name}'s performance is below expectations and requires "
            "immediate remedial support from teachers and parents."
        ),
        "Critical": (
            f"{learner_name}'s performance is critically below the expected "
            "standard. Immediate intervention, structured revision and close "
            "monitoring are required."
        ),
    }

    principal_comments = {
        "Exceeding Expectations": (
            "Excellent performance has been recorded. The learner is encouraged "
            "to maintain this high standard."
        ),
        "Excellent": (
            "Excellent performance has been recorded. The learner is encouraged "
            "to maintain this high standard."
        ),
        "Meeting Expectations": (
            "The learner is meeting expectations and should remain disciplined, "
            "focused and consistent."
        ),
        "Very Good": (
            "The learner has performed very well and should remain disciplined, "
            "focused and consistent."
        ),
        "Satisfactory": (
            "The learner should build on the progress made and work consistently "
            "to improve weaker areas."
        ),
        "Approaching Expectations": (
            "Additional effort and structured support are required to help the "
            "learner meet the expected outcomes."
        ),
        "Needs Support": (
            "The learner's performance requires improvement. Greater effort and "
            "close support from teachers and parents are recommended."
        ),
        "Below Expectations": (
            "The learner requires immediate academic intervention and close "
            "collaboration between the school and home."
        ),
        "Critical": (
            "The learner's performance requires urgent intervention. The learner "
            "should work closely with teachers and parents and demonstrate "
            "greater discipline, consistency and commitment."
        ),
    }

    return (
        scope + class_comments.get(progress, class_comments["Needs Support"]),
        scope + principal_comments.get(progress, principal_comments["Needs Support"]),
    )


def resolve_report_identity(student: Student, exam: Exam) -> ReportIdentity:
    """Resolve the learner's historical class and stream for the exam year."""

    enrollment = (
        StudentEnrollment.objects.filter(
            student=student,
            academic_year=str(exam.academic_year),
        )
        .select_related("student_class", "stream")
        .first()
    )

    if enrollment:
        return ReportIdentity(
            student_class=enrollment.student_class,
            stream=enrollment.stream,
            enrollment=enrollment,
        )

    return ReportIdentity(
        student_class=exam.student_class or student.current_class,
        stream=getattr(student, "stream", None),
        enrollment=None,
    )


def _ordered_subject_queryset(subject_ids) -> QuerySet[Subject]:
    """Return active subjects in official report-card order."""

    return Subject.objects.filter(
        id__in=subject_ids,
        is_active=True,
    ).distinct().order_by(
        "result_code",
        "category",
        "order",
        "name",
    )


def registered_subjects_for_year(
    student: Student,
    academic_year,
    student_class=None,
    *,
    enrollment: StudentEnrollment | None = None,
) -> tuple[QuerySet[Subject], str]:
    """
    Return all subjects registered to the learner for an academic year.

    Historical projects can contain subject registrations in more than one
    source. Merge every legitimate source instead of stopping at the first
    non-empty source, because an older enrollment snapshot may be incomplete.
    """

    year = str(academic_year)
    subject_ids: set[int] = set()
    registration_sources: list[str] = []

    if enrollment is None:
        enrollment = (
            StudentEnrollment.objects.filter(
                student=student,
                academic_year=year,
            )
            .select_related("student_class")
            .first()
        )

    if enrollment is not None:
        enrollment_subject_ids = set(
            StudentEnrollmentSubject.objects.filter(
                enrollment=enrollment,
                student=student,
                academic_year=year,
                is_active=True,
                subject__is_active=True,
            ).values_list("subject_id", flat=True)
        )

        if enrollment_subject_ids:
            subject_ids.update(enrollment_subject_ids)
            registration_sources.append("enrollment_registration")

    yearly_subject_ids = set(
        StudentSubject.objects.filter(
            student=student,
            academic_year=year,
            is_active=True,
            subject__is_active=True,
        ).values_list("subject_id", flat=True)
    )

    if yearly_subject_ids:
        subject_ids.update(yearly_subject_ids)
        registration_sources.append("yearly_registration")

    allow_current_fallback = (
        enrollment is None
        or bool(getattr(enrollment, "is_current", False))
    )

    if allow_current_fallback:
        yearless_subject_ids = set(
            StudentSubject.objects.filter(
                Q(academic_year="")
                | Q(academic_year__isnull=True),
                student=student,
                is_active=True,
                subject__is_active=True,
            ).values_list("subject_id", flat=True)
        )

        if yearless_subject_ids:
            subject_ids.update(yearless_subject_ids)
            registration_sources.append(
                "legacy_yearless_registration"
            )

        current_subject_ids = set(
            student.subjects.filter(
                is_active=True,
            ).values_list("id", flat=True)
        )

        if current_subject_ids:
            subject_ids.update(current_subject_ids)
            registration_sources.append("student_subjects")

    if not subject_ids:
        return Subject.objects.none(), "not_registered"

    unique_sources = list(dict.fromkeys(registration_sources))

    return (
        _ordered_subject_queryset(subject_ids),
        "+".join(unique_sources),
    )


def registered_subjects_for(
    student: Student,
    exam: Exam,
    student_class=None,
    *,
    enrollment: StudentEnrollment | None = None,
) -> tuple[QuerySet[Subject], str]:
    """
    Return every subject that belongs on the selected examination report.

    Registered subjects remain visible even when their marks are pending.
    Any subject that already has a scored StudentResult for this exam is also
    included so an incomplete registration snapshot cannot hide entered marks.
    """

    registered_queryset, registration_source = (
        registered_subjects_for_year(
            student=student,
            academic_year=exam.academic_year,
            student_class=student_class,
            enrollment=enrollment,
        )
    )

    registered_ids = set(
        registered_queryset.values_list("id", flat=True)
    )

    entered_result_subject_ids = set(
        StudentResult.objects.filter(
            student=student,
            exam=exam,
            score__isnull=False,
            subject__is_active=True,
        ).values_list("subject_id", flat=True)
    )

    report_subject_ids = registered_ids | entered_result_subject_ids

    if not report_subject_ids:
        return Subject.objects.none(), registration_source

    unregistered_result_ids = entered_result_subject_ids - registered_ids

    if unregistered_result_ids:
        if registered_ids:
            registration_source = (
                f"{registration_source}+entered_results"
            )
        else:
            registration_source = "entered_results"

    return (
        _ordered_subject_queryset(report_subject_ids),
        registration_source,
    )


def expected_subjects_for(
    student: Student,
    exam: Exam,
    student_class,
) -> QuerySet[Subject]:
    """Backward-compatible alias for registered report subjects."""

    subjects, _ = registered_subjects_for(
        student=student,
        exam=exam,
        student_class=student_class,
    )
    return subjects


def _candidate_students(exam: Exam, student_class) -> list[Student]:
    """Return learners who have results in the exam and belong to its cohort."""

    result_student_ids = StudentResult.objects.filter(
        exam=exam,
        score__isnull=False,
    ).values_list("student_id", flat=True)

    candidates = Student.objects.filter(id__in=result_student_ids).distinct()

    if student_class:
        historical_ids = StudentEnrollment.objects.filter(
            academic_year=str(exam.academic_year),
            student_class=student_class,
            student_id__in=result_student_ids,
        ).values_list("student_id", flat=True)

        if historical_ids.exists():
            candidates = candidates.filter(id__in=historical_ids)
        else:
            candidates = candidates.filter(current_class=student_class)

    return list(
        candidates.select_related("current_class", "stream").order_by(
            "admission_number",
            "last_name",
            "first_name",
        )
    )


def _student_average(
    student: Student,
    exam: Exam,
    student_class,
) -> tuple[Decimal | None, bool]:
    """Return the average for entered registered subjects and completion state."""

    identity = resolve_report_identity(student, exam)
    registered_subjects, _ = registered_subjects_for(
        student=student,
        exam=exam,
        student_class=student_class,
        enrollment=identity.enrollment,
    )
    registered_ids = set(
        registered_subjects.values_list("id", flat=True)
    )

    if not registered_ids:
        return None, False

    results = list(
        StudentResult.objects.filter(
            student=student,
            exam=exam,
            subject_id__in=registered_ids,
            score__isnull=False,
        ).select_related("subject")
    )
    result_by_subject = {
        result.subject_id: result
        for result in results
    }
    is_complete = registered_ids.issubset(result_by_subject)

    percentages = []

    for subject_id in registered_ids:
        result = result_by_subject.get(subject_id)

        if result is None:
            continue

        percentage = percentage_for_score(
            result.score,
            exam.max_score,
        )

        if percentage is not None:
            percentages.append(percentage)

    if not percentages:
        return None, False

    average = sum(percentages, ZERO) / Decimal(len(percentages))
    return average.quantize(Decimal("0.1")), is_complete


def competition_ranking(
    target_value: Decimal | None,
    values: Iterable[Decimal],
) -> Ranking:
    """Calculate a standard competition rank such as 1, 1, 3."""

    normalized_values = list(values)

    if target_value is None or not normalized_values:
        return Ranking(position=None, size=len(normalized_values))

    return Ranking(
        position=1 + sum(value > target_value for value in normalized_values),
        size=len(normalized_values),
    )


def class_ranking(
    student: Student,
    exam: Exam,
    student_class,
    *,
    target_average: Decimal,
    target_complete: bool,
) -> Ranking:
    """Rank completed reports in the same exam cohort."""

    if not target_complete:
        return Ranking(position=None, size=0)

    completed_averages: list[Decimal] = []

    for candidate in _candidate_students(exam, student_class):
        average, is_complete = _student_average(
            candidate,
            exam,
            student_class,
        )
        if average is not None and is_complete:
            completed_averages.append(average)

    return competition_ranking(target_average, completed_averages)


def subject_ranking(
    result: StudentResult,
    exam: Exam,
    candidate_ids: set[int],
) -> Ranking:
    """Rank a subject score by percentage among the same exam cohort."""

    percentages = []
    target_percentage = percentage_for_score(result.score, exam.max_score)

    queryset = StudentResult.objects.filter(
        exam=exam,
        subject=result.subject,
        score__isnull=False,
    )

    if candidate_ids:
        queryset = queryset.filter(student_id__in=candidate_ids)

    for score in queryset.values_list("score", flat=True):
        percentage = percentage_for_score(score, exam.max_score)
        if percentage is not None:
            percentages.append(percentage)

    return competition_ranking(target_percentage, percentages)


def _display_user_name(user, fallback: str) -> str:
    if user is None:
        return fallback

    full_name = user.get_full_name().strip()
    return full_name or user.get_username() or fallback


def report_staff(student_class, stream) -> tuple[object | None, object | None]:
    """Resolve stream-aware class teacher and principal."""

    class_teacher = None

    if student_class:
        stream_name = getattr(stream, "name", "") if stream else ""
        assignment = (
            ClassTeacherAssignment.objects.filter(
                class_obj=student_class,
                stream_name__iexact=stream_name,
            )
            .select_related("class_teacher")
            .first()
        )

        if assignment is None and stream_name:
            assignment = (
                ClassTeacherAssignment.objects.filter(
                    class_obj=student_class,
                    stream_name="",
                )
                .select_related("class_teacher")
                .first()
            )

        class_teacher = assignment.class_teacher if assignment else None

    if class_teacher is None and student_class:
        class_teacher = getattr(student_class, "class_teacher", None)

    principal_profile = (
        UserProfile.objects.filter(
            role="principal",
            is_approved=True,
            user__is_active=True,
        )
        .select_related("user")
        .first()
    )
    principal = principal_profile.user if principal_profile else None

    return class_teacher, principal


def _saved_teacher_comment(result: StudentResult) -> str:
    """Read a deliberate teacher comment when the active model supports it."""

    return str(getattr(result, "teacher_comment", "") or "").strip()


def build_report_context(student: Student, exam: Exam) -> dict:
    """Build the canonical HTML/PDF report from reportable exam subjects."""

    identity = resolve_report_identity(student, exam)
    registered_queryset, registration_source = registered_subjects_for(
        student=student,
        exam=exam,
        student_class=identity.student_class,
        enrollment=identity.enrollment,
    )
    registered_subjects = list(registered_queryset)
    registered_ids = {
        subject.id
        for subject in registered_subjects
    }

    result_records = (
        list(
            StudentResult.objects.filter(
                student=student,
                exam=exam,
                subject_id__in=registered_ids,
                score__isnull=False,
            )
            .select_related("subject", "grade")
            .order_by("subject__result_code", "subject__name")
        )
        if registered_ids
        else []
    )

    result_by_subject = {
        result.subject_id: result
        for result in result_records
    }
    entered_ids = set(result_by_subject)
    is_complete = bool(registered_ids) and registered_ids.issubset(
        entered_ids
    )

    candidate_ids = {
        candidate.id
        for candidate in _candidate_students(
            exam,
            identity.student_class,
        )
    }

    report_results: list[ReportResultRow] = []
    percentages: list[Decimal] = []
    total_marks = ZERO
    entered_total_possible = ZERO
    maximum_score = decimal_value(exam.max_score, "100")

    for subject in registered_subjects:
        result = result_by_subject.get(subject.id)

        if result is None:
            report_results.append(
                ReportResultRow(
                    result_id=None,
                    subject=subject,
                    score=None,
                    max_score=maximum_score,
                    percentage=None,
                    grade="—",
                    points=None,
                    progress="Pending",
                    performance_band="pending",
                    subject_position=None,
                    subject_size=0,
                    teacher_comment=(
                        "Result not entered for this registered subject."
                    ),
                    status="Pending",
                    is_entered=False,
                )
            )
            continue

        percentage = percentage_for_score(
            result.score,
            exam.max_score,
        )

        if percentage is None:
            report_results.append(
                ReportResultRow(
                    result_id=result.id,
                    subject=subject,
                    score=None,
                    max_score=maximum_score,
                    percentage=None,
                    grade="—",
                    points=None,
                    progress="Invalid",
                    performance_band="pending",
                    subject_position=None,
                    subject_size=0,
                    teacher_comment=(
                        "The recorded mark could not be converted to a valid "
                        "percentage."
                    ),
                    status="Invalid",
                    is_entered=False,
                )
            )
            continue

        resolution = resolve_grade(
            percentage_score=percentage,
            school_class=identity.student_class,
            exam=exam,
            subject=subject,
        )
        progress, band = progress_for_resolution(resolution)
        ranking = subject_ranking(result, exam, candidate_ids)
        saved_comment = _saved_teacher_comment(result)

        report_results.append(
            ReportResultRow(
                result_id=result.id,
                subject=subject,
                score=decimal_value(result.score),
                max_score=maximum_score,
                percentage=percentage,
                grade=resolution.label,
                points=resolution.points,
                progress=progress,
                performance_band=band,
                subject_position=ranking.position,
                subject_size=ranking.size,
                teacher_comment=(
                    saved_comment
                    or subject_comment(
                        subject.name,
                        progress,
                        partial_report=not is_complete,
                    )
                ),
                status="Entered",
                is_entered=True,
            )
        )

        percentages.append(percentage)
        total_marks += decimal_value(result.score)
        entered_total_possible += maximum_score

    has_recorded_results = bool(percentages)
    overall_average = (
        (sum(percentages, ZERO) / Decimal(len(percentages))).quantize(
            Decimal("0.1")
        )
        if percentages
        else ZERO
    )

    if has_recorded_results:
        overall_resolution = resolve_grade(
            percentage_score=overall_average,
            school_class=identity.student_class,
            exam=exam,
            subject=None,
        )
        overall_grade = overall_resolution.label
        overall_progress, overall_band = progress_for_resolution(
            overall_resolution
        )
    else:
        overall_grade = "—"
        overall_progress = "Pending"
        overall_band = "pending"

    ranking = class_ranking(
        student,
        exam,
        identity.student_class,
        target_average=overall_average,
        target_complete=is_complete,
    )

    learner_name = student.first_name or "The learner"

    if has_recorded_results:
        class_teacher_comment, principal_comment = overall_comments(
            learner_name,
            overall_progress,
            is_complete=is_complete,
            recorded_subjects=len(entered_ids & registered_ids),
            expected_subjects=len(registered_subjects),
        )
    elif registered_subjects:
        class_teacher_comment = (
            f"No marks have been entered for {learner_name}'s registered "
            "subjects. Academic remarks will be available after result entry."
        )
        principal_comment = (
            "The report is awaiting result entry for the learner's registered "
            "subjects."
        )
    else:
        class_teacher_comment = (
            f"No subject registration was found for {learner_name} in "
            f"{exam.academic_year}."
        )
        principal_comment = (
            "Subject registration must be completed before an academic report "
            "can be issued."
        )

    class_teacher, principal = report_staff(
        identity.student_class,
        identity.stream,
    )

    school = SchoolSetting.objects.first()
    recorded_subject_count = len(entered_ids & registered_ids)
    registered_subject_count = len(registered_subjects)
    pending_subject_count = max(
        registered_subject_count - recorded_subject_count,
        0,
    )
    completion_percentage = (
        (
            Decimal(recorded_subject_count)
            / Decimal(registered_subject_count)
            * HUNDRED
        ).quantize(Decimal("0.1"))
        if registered_subject_count
        else ZERO
    )
    registered_total_possible = (
        maximum_score * Decimal(registered_subject_count)
    )

    if not registered_subjects:
        report_status = "Registration Required"
        warning = (
            "No registered subjects were found for this learner and academic "
            "year. Register the learner's subjects before entering results."
        )
    elif not is_complete:
        report_status = "Incomplete"
        warning = (
            "This report includes the learner's registered subjects and any "
            "subjects with entered results for this exam. Registered subjects "
            "without marks are shown as Pending."
        )
    else:
        report_status = "Draft"
        warning = ""

    return {
        "student": student,
        "exam": exam,
        "results": report_results,
        "report_class": identity.student_class,
        "report_stream": identity.stream,
        "school": school,
        "school_name": getattr(school, "name", "") if school else "",
        "school_motto": getattr(school, "motto", "") if school else "",
        "school_address": getattr(school, "address", "") if school else "",
        "school_phone": getattr(school, "phone", "") if school else "",
        "school_email": getattr(school, "email", "") if school else "",
        "school_logo": (
            school.logo.url
            if school and getattr(school, "logo", None)
            else ""
        ),
        "total_marks": total_marks,
        "total_possible": entered_total_possible,
        "registered_total_possible": registered_total_possible,
        "overall_average": overall_average,
        "overall_grade": overall_grade,
        "overall_progress": overall_progress,
        "overall_band": overall_band,
        "has_recorded_results": has_recorded_results,
        "class_position": ranking.position,
        "class_size": ranking.size,
        "registered_subject_count": registered_subject_count,
        "expected_subject_count": registered_subject_count,
        "recorded_subject_count": recorded_subject_count,
        "pending_subject_count": pending_subject_count,
        "completion_percentage": completion_percentage,
        "subject_registration_source": registration_source,
        "is_complete": is_complete,
        "is_partial_report": not is_complete,
        "report_status": report_status,
        "report_warning": warning,
        "class_teacher_comment": class_teacher_comment,
        "principal_comment": principal_comment,
        "class_teacher_name": _display_user_name(
            class_teacher,
            "Class Teacher",
        ),
        "principal_name": _display_user_name(
            principal,
            "School Principal",
        ),
        "generated_at": timezone.now(),
        "report_id": f"RPT-{exam.id}-{student.id}",
    }
