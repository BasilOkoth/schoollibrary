from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TeachingAssignment(models.Model):
    """
    Authoritative result-entry assignment.

    A teacher is assigned a subject in a class and either:
    - one specific stream; or
    - every stream when stream is left blank.
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="result_teaching_assignments",
    )

    subject = models.ForeignKey(
        "digitallibrary.Subject",
        on_delete=models.CASCADE,
        related_name="result_teaching_assignments",
    )

    school_class = models.ForeignKey(
        "digitallibrary.Class",
        on_delete=models.CASCADE,
        related_name="result_teaching_assignments",
    )

    stream = models.ForeignKey(
        "digitallibrary.ClassStream",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="result_teaching_assignments",
        help_text=(
            "Choose a stream. Leave blank only when this teacher "
            "handles the subject in every stream of the class."
        ),
    )

    academic_year = models.CharField(
        max_length=9,
        db_index=True,
        help_text="Use exactly the same academic year shown on the exam.",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_result_teaching_assignments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-academic_year",
            "school_class__sort_order",
            "school_class__name",
            "stream__name",
            "subject__name",
            "teacher__first_name",
            "teacher__last_name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "teacher",
                    "subject",
                    "school_class",
                    "academic_year",
                ],
                condition=Q(stream__isnull=True),
                name="rs_unique_all_streams",
            ),
            models.UniqueConstraint(
                fields=[
                    "teacher",
                    "subject",
                    "school_class",
                    "stream",
                    "academic_year",
                ],
                condition=Q(stream__isnull=False),
                name="rs_unique_one_stream",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "teacher",
                    "subject",
                    "school_class",
                    "academic_year",
                    "is_active",
                ],
                name="rs_teacher_scope_idx",
            ),
            models.Index(
                fields=[
                    "school_class",
                    "stream",
                    "subject",
                ],
                name="rs_class_stream_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.stream_id
            and self.school_class_id
            and self.stream.school_class_id != self.school_class_id
        ):
            raise ValidationError(
                {
                    "stream": (
                        "The selected stream does not belong to "
                        "the selected class."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        teacher_name = self.teacher.get_full_name() or self.teacher.username
        stream_name = self.stream.name if self.stream_id else "All streams"

        return (
            f"{teacher_name} - {self.subject} - "
            f"{self.school_class} - {stream_name} "
            f"({self.academic_year})"
        )
