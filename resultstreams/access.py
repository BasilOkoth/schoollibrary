from digitallibrary.models import ClassStream, Student

from .models import TeachingAssignment


RESULT_MANAGER_ROLES = {
    "admin",
    "principal",
    "deputy_principal",
    "director_of_studies",
}


def get_user_role(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", "")


def can_manage_all_results(user):
    return bool(
        user.is_superuser
        or get_user_role(user) in RESULT_MANAGER_ROLES
    )


def exam_academic_year(exam):
    return str(getattr(exam, "academic_year", "") or "").strip()


def scope_assignments(*, user, exam, school_class, subject):
    return TeachingAssignment.objects.filter(
        teacher=user,
        subject=subject,
        school_class=school_class,
        academic_year=exam_academic_year(exam),
        is_active=True,
    )


def teacher_has_scope_access(*, user, exam, school_class, subject):
    if can_manage_all_results(user):
        return True

    return scope_assignments(
        user=user,
        exam=exam,
        school_class=school_class,
        subject=subject,
    ).exists()


def allowed_streams_for_user(*, user, exam, school_class, subject):
    all_streams = ClassStream.objects.filter(
        school_class=school_class,
        is_active=True,
    ).order_by("name")

    if can_manage_all_results(user):
        return all_streams

    assignments = scope_assignments(
        user=user,
        exam=exam,
        school_class=school_class,
        subject=subject,
    )

    # Blank stream means the teacher handles all streams in that class.
    if assignments.filter(stream__isnull=True).exists():
        return all_streams

    stream_ids = assignments.filter(stream__isnull=False).values_list(
        "stream_id",
        flat=True,
    )

    return all_streams.filter(id__in=stream_ids)


def eligible_students(*, school_class, subject, stream=None):
    """
    Return active students in the selected class and stream.

    Compulsory subjects always include every active student in scope.

    For elective subjects, Student.subjects is used only after subject
    enrolments have actually been configured for the selected class/stream.
    Until then, all active students are returned so existing schools are not
    blocked from entering results.
    """

    students = Student.objects.filter(
        current_class=school_class,
        is_active=True,
    )

    if stream is not None:
        students = students.filter(
            stream=stream,
        )

    if not getattr(subject, "is_compulsory", False):
        subject_assignments_exist = students.filter(
            subjects__isnull=False,
        ).exists()

        if subject_assignments_exist:
            students = students.filter(
                subjects=subject,
            )

    return (
        students
        .select_related(
            "current_class",
            "stream",
        )
        .distinct()
        .order_by(
            "admission_number",
            "last_name",
            "first_name",
        )
    )
