# File: timetable/generator_models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TimetableRequirement(models.Model):
    """Weekly teaching load used by the automatic timetable generator."""

    template = models.ForeignKey(
        "timetable.TimetableTemplate",
        on_delete=models.CASCADE,
        related_name="requirements",
    )
    class_group = models.ForeignKey(
        "digitallibrary.Class",
        on_delete=models.CASCADE,
        related_name="timetable_requirements",
    )
    stream = models.ForeignKey(
        "digitallibrary.ClassStream",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="timetable_requirements",
    )
    apply_to_all_streams = models.BooleanField(
        default=False,
        help_text=(
            "Create this weekly requirement separately for every active stream "
            "in the selected class."
        ),
    )
    subject = models.ForeignKey(
        "digitallibrary.Subject",
        on_delete=models.CASCADE,
        related_name="timetable_requirements",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_requirements",
    )
    room = models.ForeignKey(
        "timetable.TimetableRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_requirements",
    )
    lessons_per_week = models.PositiveSmallIntegerField(
        default=4,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(20),
        ],
        help_text="Total teaching periods required each week.",
    )
    consecutive_periods = models.PositiveSmallIntegerField(
        default=1,
        choices=[
            (1, "Single period"),
            (2, "Double period"),
        ],
        help_text=(
            "Choose Double period when every session must use two adjacent "
            "teaching periods."
        ),
    )
    lesson_group = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Optional learner group, e.g. Business option. Parallel subjects "
            "must use different lesson-group names."
        ),
    )
    parallel_block = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Give subjects that must run at the same time the same block name, "
            "e.g. FORM3_OPTIONS."
        ),
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_timetable_requirements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "class_group__sort_order",
            "class_group__name",
            "stream__name",
            "parallel_block",
            "subject__name",
        ]
        indexes = [
            models.Index(
                fields=["template", "class_group", "stream", "is_active"],
                name="tt_req_scope_active_idx",
            ),
            models.Index(
                fields=["template", "parallel_block", "is_active"],
                name="tt_req_parallel_idx",
            ),
        ]

    def __str__(self):
        scope = self.class_group.name
        if self.apply_to_all_streams:
            scope = f"{scope} - All streams separately"
        elif self.stream:
            scope = f"{scope} {self.stream.name}"
        else:
            scope = f"{scope} - Whole class"

        return f"{scope}: {self.subject.name} ({self.lessons_per_week}/week)"

    def clean(self):
        super().clean()

        self.lesson_group = (self.lesson_group or "").strip()
        self.parallel_block = (self.parallel_block or "").strip()

        if (
            self.stream_id
            and self.class_group_id
            and self.stream.school_class_id != self.class_group_id
        ):
            raise ValidationError(
                {"stream": "The selected stream does not belong to this class."}
            )

        if self.apply_to_all_streams and self.stream_id:
            raise ValidationError(
                {
                    "stream": (
                        "Leave Stream blank when Apply to all streams is selected."
                    )
                }
            )

        if self.parallel_block and not self.lesson_group:
            raise ValidationError(
                {
                    "lesson_group": (
                        "Parallel subjects need a Lesson / Elective Group name."
                    )
                }
            )

        if (
            self.consecutive_periods == 2
            and self.lessons_per_week
            and self.lessons_per_week % 2
        ):
            raise ValidationError(
                {
                    "lessons_per_week": (
                        "Double-period requirements must use an even number of "
                        "periods per week."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.lesson_group = (self.lesson_group or "").strip()
        self.parallel_block = (self.parallel_block or "").strip()
        super().save(*args, **kwargs)


class TimetableGenerationDraft(models.Model):
    """Server-side preview payload for the automatic timetable generator."""

    template = models.ForeignKey(
        "timetable.TimetableTemplate",
        on_delete=models.CASCADE,
        related_name="generation_drafts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timetable_generation_drafts",
    )
    proposals = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    is_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["template", "created_by", "is_applied"],
                name="tt_draft_owner_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.template.name} preview #{self.pk} "
            f"by {self.created_by}"
        )
