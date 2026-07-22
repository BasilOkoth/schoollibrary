from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models


class ExamSubjectComponent(models.Model):
    """
    Weighted assessment component.

    Examples:
        Theory — 60%
        Practical — 40%
        Overall — 100%
    """

    exam = models.ForeignKey(
        "digitallibrary.Exam",
        on_delete=models.CASCADE,
        related_name="subject_components",
    )

    subject = models.ForeignKey(
        "digitallibrary.Subject",
        on_delete=models.PROTECT,
        related_name="exam_components",
    )

    name = models.CharField(
        max_length=80,
        help_text=(
            "Examples: Theory, Practical, Oral, "
            "Project or Overall."
        ),
    )

    weight_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100.00")),
        ],
        help_text=(
            "Contribution to the final result, "
            "for example 60 or 40."
        ),
    )

    order = models.PositiveSmallIntegerField(
        default=1,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configured_exam_components",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "subject__name",
            "order",
            "name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "exam",
                    "subject",
                    "name",
                ],
                name="unique_exam_subject_component",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        weight_percentage__gt=0
                    )
                    & models.Q(
                        weight_percentage__lte=100
                    )
                ),
                name="exam_component_weight_valid",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "exam",
                    "subject",
                    "order",
                ],
                name="exam_subject_component_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.subject.name} - "
            f"{self.name} "
            f"({self.weight_percentage}%)"
        )

    def clean(self):
        super().clean()

        self.name = (
            self.name or ""
        ).strip()

        if not self.name:
            raise ValidationError(
                {
                    "name": (
                        "Enter a component name such as "
                        "Theory, Practical or Overall."
                    )
                }
            )

        if self.weight_percentage is None:
            raise ValidationError(
                {
                    "weight_percentage": (
                        "Enter the component contribution."
                    )
                }
            )

        weight = Decimal(
            self.weight_percentage
        )

        if (
            weight <= 0
            or weight > Decimal("100.00")
        ):
            raise ValidationError(
                {
                    "weight_percentage": (
                        "The contribution must be "
                        "greater than 0 and no more "
                        "than 100."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )


class ExamSubjectPaper(models.Model):
    """
    One raw-mark paper belonging to a component.
    """

    component = models.ForeignKey(
        ExamSubjectComponent,
        on_delete=models.CASCADE,
        related_name="papers",
    )

    paper_name = models.CharField(
        max_length=80,
        help_text=(
            "Examples: Paper 1, Paper 2, "
            "Practical or Oral."
        ),
    )

    max_marks = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01")
            ),
            MaxValueValidator(
                Decimal("1000.00")
            ),
        ],
        help_text=(
            "Maximum raw mark, such as "
            "40, 50, 80, 90 or 100."
        ),
    )

    order = models.PositiveSmallIntegerField(
        default=1,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configured_exam_papers",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "component__order",
            "order",
            "paper_name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "component",
                    "paper_name",
                ],
                name="unique_component_paper_name",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    max_marks__gt=0
                ),
                name=(
                    "exam_subject_paper_"
                    "max_marks_positive"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "component",
                    "order",
                ],
                name="component_paper_lookup_idx",
            ),
        ]

    @property
    def exam(self):
        return self.component.exam

    @property
    def exam_id(self):
        return self.component.exam_id

    @property
    def subject(self):
        return self.component.subject

    @property
    def subject_id(self):
        return self.component.subject_id

    def __str__(self):
        return (
            f"{self.component.name} - "
            f"{self.paper_name}/"
            f"{self.max_marks}"
        )

    def clean(self):
        super().clean()

        self.paper_name = (
            self.paper_name or ""
        ).strip()

        if not self.paper_name:
            raise ValidationError(
                {
                    "paper_name": (
                        "Enter a paper name."
                    )
                }
            )

        if self.max_marks is None:
            raise ValidationError(
                {
                    "max_marks": (
                        "Enter the maximum marks."
                    )
                }
            )

        maximum = Decimal(
            self.max_marks
        )

        if maximum <= 0:
            raise ValidationError(
                {
                    "max_marks": (
                        "Maximum marks must be "
                        "greater than zero."
                    )
                }
            )

        if not self.pk:
            return

        previous = (
            ExamSubjectPaper.objects
            .filter(
                pk=self.pk
            )
            .values(
                "component_id",
                "paper_name",
                "max_marks",
            )
            .first()
        )

        if not previous:
            return

        changed = (
            previous["component_id"]
            != self.component_id
            or previous["paper_name"]
            != self.paper_name
            or Decimal(
                previous["max_marks"]
            )
            != maximum
        )

        if (
            changed
            and self.student_marks.exists()
        ):
            raise ValidationError(
                "This paper already has pupil marks. "
                "Its component, name and maximum "
                "marks cannot be changed."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )


class StudentPaperMark(models.Model):
    """
    Raw mark scored by one pupil in one paper.
    """

    student = models.ForeignKey(
        "digitallibrary.Student",
        on_delete=models.CASCADE,
        related_name="exam_paper_marks",
    )

    paper = models.ForeignKey(
        ExamSubjectPaper,
        on_delete=models.PROTECT,
        related_name="student_marks",
    )

    raw_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.00")
            ),
        ],
    )

    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_exam_paper_marks",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "paper__component__order",
            "paper__order",
            "paper__paper_name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "paper",
                ],
                name=(
                    "unique_student_mark_"
                    "per_exam_paper"
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    raw_score__gte=0
                ),
                name=(
                    "student_paper_mark_"
                    "nonnegative"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "paper",
                ],
                name=(
                    "student_paper_mark_"
                    "lookup_idx"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.paper.paper_name}: "
            f"{self.raw_score}/"
            f"{self.paper.max_marks}"
        )

    def clean(self):
        super().clean()

        if self.raw_score is None:
            raise ValidationError(
                {
                    "raw_score": (
                        "Enter the pupil's mark."
                    )
                }
            )

        raw_score = Decimal(
            self.raw_score
        )

        if raw_score < 0:
            raise ValidationError(
                {
                    "raw_score": (
                        "The mark cannot be negative."
                    )
                }
            )

        if self.paper_id:
            maximum = Decimal(
                self.paper.max_marks
            )

            if raw_score > maximum:
                raise ValidationError(
                    {
                        "raw_score": (
                            f"The mark cannot exceed "
                            f"{maximum} for "
                            f"{self.paper.paper_name}."
                        )
                    }
                )

        if (
            self.student_id
            and self.paper_id
            and self.paper.exam.student_class_id
            and self.student.current_class_id
            and self.paper.exam.student_class_id
            != self.student.current_class_id
        ):
            raise ValidationError(
                "This pupil does not belong to "
                "the class assigned to this exam."
            )

    def save(self, *args, **kwargs):
        self.full_clean()

        return super().save(
            *args,
            **kwargs,
        )
