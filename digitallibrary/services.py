from django.db import transaction
from django.utils import timezone

from .models import (
    Student,
    Subject,
    StudentSubject,
    StudentActionLog,
    StudentEnrollment,
    StudentEnrollmentSubject,
)


def get_students_for_promotion(
    from_class,
    from_stream=None,
):
    """
    Return active students in the selected class and optional stream.
    """

    students = Student.objects.filter(
        current_class=from_class,
        is_active=True,
        status="active",
    ).select_related(
        "current_class",
        "stream",
    ).order_by(
        "last_name",
        "first_name",
        "admission_number",
    )

    if from_stream:
        students = students.filter(stream=from_stream)

    return students


def get_or_create_current_enrollment(
    student,
    academic_year,
    student_class,
    stream=None,
    user=None,
):
    """
    Creates the old/current enrollment if it does not already exist.

    This is important because ShuleHub already has students with current_class
    but may not yet have StudentEnrollment history records.
    """

    enrollment, created = StudentEnrollment.objects.get_or_create(
        student=student,
        academic_year=academic_year,
        defaults={
            "student_class": student_class,
            "stream": stream,
            "pathway": student.pathway or "",
            "is_current": True,
            "status": StudentEnrollment.STATUS_ACTIVE,
            "created_by": user,
        },
    )

    if not created:
        changed = False

        if enrollment.student_class_id != student_class.id:
            enrollment.student_class = student_class
            changed = True

        if stream and enrollment.stream_id != stream.id:
            enrollment.stream = stream
            changed = True

        if not enrollment.is_current:
            enrollment.is_current = True
            changed = True

        if enrollment.status != StudentEnrollment.STATUS_ACTIVE:
            enrollment.status = StudentEnrollment.STATUS_ACTIVE
            changed = True

        if changed:
            enrollment.save()

    return enrollment


def assign_subjects_for_enrollment(
    student,
    enrollment,
    academic_year,
):
    """
    Assign subjects based on the student's current class and pathway.

    Updates:
    - Student.subjects ManyToMany field for current usage
    - StudentSubject simple current-subject tracking table
    - StudentEnrollmentSubject historical subject table
    """

    allowed_subjects = student.get_allowed_subjects()

    # Update current subject list.
    student.subjects.set(allowed_subjects)

    # Update simple current StudentSubject table.
    StudentSubject.objects.filter(student=student).delete()

    current_subject_rows = [
        StudentSubject(
            student=student,
            subject=subject,
        )
        for subject in allowed_subjects
    ]

    if current_subject_rows:
        StudentSubject.objects.bulk_create(
            current_subject_rows,
            ignore_conflicts=True,
        )

    # Store historical subjects for this enrollment.
    enrollment_subject_rows = [
        StudentEnrollmentSubject(
            enrollment=enrollment,
            student=student,
            subject=subject,
            academic_year=academic_year,
            is_active=True,
        )
        for subject in allowed_subjects
    ]

    if enrollment_subject_rows:
        StudentEnrollmentSubject.objects.bulk_create(
            enrollment_subject_rows,
            ignore_conflicts=True,
        )

    return allowed_subjects.count()


@transaction.atomic
def promote_students(
    *,
    user,
    promotion_action,
    from_academic_year,
    to_academic_year,
    from_class,
    from_stream=None,
    to_class=None,
    to_stream=None,
    selected_student_ids=None,
    assign_subjects=True,
    default_pathway="",
):
    """
    Main class promotion engine.

    It does not delete marks, reports, fees, or old class data.

    For promotion/repetition:
        - closes old enrollment
        - creates new enrollment
        - updates Student.current_class for current system compatibility
        - assigns new class subjects

    For completion:
        - marks old enrollment completed
        - marks student graduated
    """

    if selected_student_ids is None:
        selected_student_ids = []

    selected_student_ids = [
        int(student_id)
        for student_id in selected_student_ids
        if str(student_id).isdigit()
    ]

    students = get_students_for_promotion(
        from_class=from_class,
        from_stream=from_stream,
    ).select_for_update(of=("self",))

    if selected_student_ids:
        students = students.filter(id__in=selected_student_ids)

    promoted_count = 0
    repeated_count = 0
    completed_count = 0
    skipped_count = 0
    subject_count = 0

    skipped_students = []

    for student in students:
        old_enrollment = get_or_create_current_enrollment(
            student=student,
            academic_year=from_academic_year,
            student_class=from_class,
            stream=student.stream,
            user=user,
        )

        # Completion / graduation.
        if promotion_action == "complete":
            old_enrollment.is_current = False
            old_enrollment.status = StudentEnrollment.STATUS_COMPLETED
            old_enrollment.save(
                update_fields=[
                    "is_current",
                    "status",
                    "updated_at",
                ]
            )

            student.status = "graduated"
            student.is_active = False
            student.transfer_reason = "graduated"
            student.transfer_date = timezone.now().date()
            student.save(
                update_fields=[
                    "status",
                    "is_active",
                    "transfer_reason",
                    "transfer_date",
                    "updated_at",
                ]
            )

            StudentActionLog.objects.create(
                student=student,
                action="graduated",
                performed_by=user,
                reason="Student marked as completed during class promotion.",
                details={
                    "from_academic_year": from_academic_year,
                    "from_class": from_class.name,
                    "completed_at": timezone.now().isoformat(),
                },
            )

            completed_count += 1
            continue

        # Promotion or repetition requires a target class.
        if not to_class:
            skipped_count += 1
            skipped_students.append(
                {
                    "student": student.get_full_name(),
                    "reason": "Target class was not selected.",
                }
            )
            continue

        # Prevent double enrollment in target year.
        existing_target_enrollment = StudentEnrollment.objects.filter(
            student=student,
            academic_year=to_academic_year,
        ).first()

        if existing_target_enrollment:
            skipped_count += 1
            skipped_students.append(
                {
                    "student": student.get_full_name(),
                    "reason": (
                        f"Already has enrollment for {to_academic_year}."
                    ),
                }
            )
            continue

        # If target class requires pathway, student must have one or a default must be supplied.
        target_pathway = student.pathway or ""

        if to_class.requires_pathway:
            if default_pathway:
                target_pathway = default_pathway

            if not target_pathway:
                skipped_count += 1
                skipped_students.append(
                    {
                        "student": student.get_full_name(),
                        "reason": (
                            f"{to_class.name} requires a pathway, but no pathway was provided."
                        ),
                    }
                )
                continue
        else:
            target_pathway = ""

        # Close old active enrollment.
        old_enrollment.is_current = False

        if promotion_action == "repeat":
            old_enrollment.status = StudentEnrollment.STATUS_REPEATED
        else:
            old_enrollment.status = StudentEnrollment.STATUS_PROMOTED

        old_enrollment.save(
            update_fields=[
                "is_current",
                "status",
                "updated_at",
            ]
        )

        # Ensure no other enrollment is marked current for this student.
        StudentEnrollment.objects.filter(
            student=student,
            is_current=True,
        ).exclude(
            id=old_enrollment.id,
        ).update(
            is_current=False,
            status=StudentEnrollment.STATUS_INACTIVE,
        )

        # Create new enrollment.
        new_enrollment = StudentEnrollment.objects.create(
            student=student,
            academic_year=to_academic_year,
            student_class=to_class,
            stream=to_stream,
            pathway=target_pathway,
            is_current=True,
            status=StudentEnrollment.STATUS_ACTIVE,
            promoted_from=old_enrollment,
            created_by=user,
        )

        # Update Student.current_class so existing dashboards, fees, exams and reports continue working.
        student.current_class = to_class
        student.stream = to_stream
        student.pathway = target_pathway
        student.status = "active"
        student.is_active = True
        student.save(
            update_fields=[
                "current_class",
                "stream",
                "pathway",
                "status",
                "is_active",
                "updated_at",
            ]
        )

        if assign_subjects:
            subject_count += assign_subjects_for_enrollment(
                student=student,
                enrollment=new_enrollment,
                academic_year=to_academic_year,
            )

        if promotion_action == "repeat":
            repeated_count += 1
            log_action = "repeated"
            reason = (
                f"Student repeated {from_class.name} "
                f"from {from_academic_year} to {to_academic_year}."
            )
        else:
            promoted_count += 1
            log_action = "promoted"
            reason = (
                f"Student promoted from {from_class.name} "
                f"to {to_class.name}."
            )

        StudentActionLog.objects.create(
            student=student,
            action=log_action,
            performed_by=user,
            reason=reason,
            details={
                "promotion_action": promotion_action,
                "from_academic_year": from_academic_year,
                "to_academic_year": to_academic_year,
                "from_class_id": from_class.id,
                "from_class": from_class.name,
                "to_class_id": to_class.id,
                "to_class": to_class.name,
                "from_stream": from_stream.name if from_stream else "",
                "to_stream": to_stream.name if to_stream else "",
                "subjects_assigned": assign_subjects,
                "pathway": target_pathway,
            },
        )

    return {
        "promoted_count": promoted_count,
        "repeated_count": repeated_count,
        "completed_count": completed_count,
        "skipped_count": skipped_count,
        "subject_count": subject_count,
        "skipped_students": skipped_students,
    }
