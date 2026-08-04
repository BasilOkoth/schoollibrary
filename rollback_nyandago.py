from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from digitallibrary.models import (
    Class,
    Student,
    StudentEnrollmentSubject,
    StudentSubject,
    Subject,
)

ACADEMIC_YEAR = "2026"
CORE_REGEX = r"^(English|Kiswahili|Mathematics)$"
BATCH_WIDTH = timedelta(minutes=3)
MAXIMUM_BATCH_AGE = timedelta(hours=2)

classes = list(Class.objects.filter(name__iregex=r"^form\s*[34]$"))
students = Student.objects.filter(current_class__in=classes)

student_subject_scope = (
    StudentSubject.objects.filter(
        student__in=students,
        academic_year=ACADEMIC_YEAR,
        is_active=True,
    )
    .exclude(subject__name__iregex=CORE_REGEX)
)

enrollment_subject_scope = (
    StudentEnrollmentSubject.objects.filter(
        student__in=students,
        academic_year=ACADEMIC_YEAR,
        is_active=True,
    )
    .exclude(subject__name__iregex=CORE_REGEX)
)

latest_student_subject = student_subject_scope.aggregate(
    value=Max("created_at")
)["value"]
latest_enrollment_subject = enrollment_subject_scope.aggregate(
    value=Max("assigned_at")
)["value"]

now = timezone.now()

if not latest_student_subject and not latest_enrollment_subject:
    raise RuntimeError("No active non-core batch found.")

if (
    latest_student_subject
    and now - latest_student_subject > MAXIMUM_BATCH_AGE
):
    raise RuntimeError(
        f"Latest StudentSubject batch is too old: {latest_student_subject}"
    )

if (
    latest_enrollment_subject
    and now - latest_enrollment_subject > MAXIMUM_BATCH_AGE
):
    raise RuntimeError(
        "Latest StudentEnrollmentSubject batch is too old: "
        f"{latest_enrollment_subject}"
    )

student_subject_candidates = student_subject_scope.none()
enrollment_subject_candidates = enrollment_subject_scope.none()

if latest_student_subject:
    student_subject_candidates = student_subject_scope.filter(
        created_at__gte=latest_student_subject - BATCH_WIDTH
    )

if latest_enrollment_subject:
    enrollment_subject_candidates = enrollment_subject_scope.filter(
        assigned_at__gte=latest_enrollment_subject - BATCH_WIDTH
    )

pairs = set(
    student_subject_candidates.values_list("student_id", "subject_id")
)
pairs.update(
    enrollment_subject_candidates.values_list("student_id", "subject_id")
)

if not pairs:
    raise RuntimeError("No rollback candidates found.")

subjects_field = Student._meta.get_field("subjects")
through_model = subjects_field.remote_field.through

if not through_model._meta.auto_created:
    raise RuntimeError(
        "Student.subjects uses a custom through model; rollback aborted."
    )

student_field_name = subjects_field.m2m_field_name()
subject_field_name = subjects_field.m2m_reverse_field_name()

with transaction.atomic():
    applicable_electives = (
        Subject.objects.filter(applicable_classes__in=classes)
        .exclude(name__iregex=CORE_REGEX)
        .distinct()
    )

    for subject in applicable_electives:
        subject.applicable_classes.remove(*classes)

    removed_m2m = 0

    for student_id, subject_id in pairs:
        deleted, _ = through_model.objects.filter(
            **{
                f"{student_field_name}_id": student_id,
                f"{subject_field_name}_id": subject_id,
            }
        ).delete()
        removed_m2m += deleted

    deactivated_student_subjects = student_subject_candidates.update(
        is_active=False
    )
    deactivated_enrollments = enrollment_subject_candidates.update(
        is_active=False
    )

print(
    "Rollback complete:",
    f"StudentSubject={deactivated_student_subjects},",
    f"Enrollment={deactivated_enrollments},",
    f"M2M={removed_m2m}",
)

for school_class in classes:
    subjects = list(
        Subject.objects.filter(
            applicable_classes=school_class,
            is_active=True,
        )
        .order_by("name")
        .values_list("name", flat=True)
    )
    print(school_class.name, subjects)
