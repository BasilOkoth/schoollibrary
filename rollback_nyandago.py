from csv import writer
from datetime import datetime, timezone

from django.db import transaction
from digitallibrary.models import (
    Class,
    Student,
    StudentEnrollmentSubject,
    StudentSubject,
    Subject,
)

ACADEMIC_YEAR = "2026"
CORE_NAMES = {"english", "kiswahili", "mathematics"}

classes = list(Class.objects.filter(name__iregex=r"^form\s*[34]$"))
students = Student.objects.filter(current_class__in=classes)
student_ids = list(students.values_list("id", flat=True))

non_core_subjects = [
    subject
    for subject in Subject.objects.filter(is_active=True)
    if subject.name.strip().casefold() not in CORE_NAMES
]
non_core_subject_ids = [subject.id for subject in non_core_subjects]

active_student_subjects = StudentSubject.objects.filter(
    student_id__in=student_ids,
    academic_year=ACADEMIC_YEAR,
    is_active=True,
)

active_enrollment_subjects = StudentEnrollmentSubject.objects.filter(
    student_id__in=student_ids,
    academic_year=ACADEMIC_YEAR,
    is_active=True,
)

timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup_path = f"nyandago_legacy_subject_backup_{timestamp}.csv"

with open(backup_path, "w", newline="", encoding="utf-8") as backup_file:
    csv_writer = writer(backup_file)
    csv_writer.writerow(
        [
            "source",
            "row_id",
            "student_id",
            "admission_number",
            "student_name",
            "class",
            "subject_id",
            "subject",
            "academic_year",
            "timestamp",
        ]
    )

    for row in active_student_subjects.select_related(
        "student",
        "student__current_class",
        "subject",
    ):
        csv_writer.writerow(
            [
                "StudentSubject",
                row.id,
                row.student_id,
                row.student.admission_number,
                row.student.get_full_name(),
                row.student.current_class.name if row.student.current_class else "",
                row.subject_id,
                row.subject.name,
                row.academic_year,
                row.created_at.isoformat(),
            ]
        )

    for row in active_enrollment_subjects.select_related(
        "student",
        "student__current_class",
        "subject",
    ):
        csv_writer.writerow(
            [
                "StudentEnrollmentSubject",
                row.id,
                row.student_id,
                row.student.admission_number,
                row.student.get_full_name(),
                row.student.current_class.name if row.student.current_class else "",
                row.subject_id,
                row.subject.name,
                row.academic_year,
                row.assigned_at.isoformat(),
            ]
        )

student_subject_rows = active_student_subjects.filter(
    subject_id__in=non_core_subject_ids,
)

enrollment_subject_rows = active_enrollment_subjects.filter(
    subject_id__in=non_core_subject_ids,
)

subjects_field = Student._meta.get_field("subjects")
through_model = subjects_field.remote_field.through

if not through_model._meta.auto_created:
    raise RuntimeError(
        "Student.subjects uses a custom through model; cleanup aborted."
    )

student_field_name = subjects_field.m2m_field_name()
subject_field_name = subjects_field.m2m_reverse_field_name()

with transaction.atomic():
    for subject in non_core_subjects:
        subject.applicable_classes.remove(*classes)

    removed_m2m, _ = through_model.objects.filter(
        **{
            f"{student_field_name}_id__in": student_ids,
            f"{subject_field_name}_id__in": non_core_subject_ids,
        }
    ).delete()

    deactivated_student_subjects = student_subject_rows.update(
        is_active=False
    )
    deactivated_enrollments = enrollment_subject_rows.update(
        is_active=False
    )

print(f"Backup written: {backup_path}")
print(f"Form 3/Form 4 learners: {len(student_ids)}")
print(f"StudentSubject rows deactivated: {deactivated_student_subjects}")
print(f"Enrollment rows deactivated: {deactivated_enrollments}")
print(f"Student-subject M2M links removed: {removed_m2m}")

for school_class in classes:
    remaining = list(
        Subject.objects.filter(
            applicable_classes=school_class,
            is_active=True,
        )
        .order_by("name")
        .values_list("name", flat=True)
    )
    print(f"{school_class.name}: {remaining}")
