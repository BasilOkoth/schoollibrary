from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from decimal import Decimal

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class ExamSubjectComponent(models.Model):
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
        help_text="Examples: Theory, Practical, Oral or Project.",
    )

    weight_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100.00")),
        ],
        help_text="Contribution to the final result, for example 60 or 40.",
    )

    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["order", "name"]

        constraints = [
            models.UniqueConstraint(
                fields=["exam", "subject", "name"],
                name="unique_exam_subject_component",
            )
        ]

    def __str__(self):
        return (
            f"{self.subject.name} - {self.name} "
            f"({self.weight_percentage}%)"
        )
class ExamSubjectPaper(models.Model):
    """
    Defines one paper belonging to a subject in a particular exam.

    Examples:
        Biology Paper 1 / 80
        Biology Paper 2 / 80
        Biology Paper 3 / 40
        Chemistry Practical / 50
    """

    exam = models.ForeignKey(
        "digitallibrary.Exam",
        on_delete=models.CASCADE,
        related_name="configured_subject_papers",
    )

    subject = models.ForeignKey(
        "digitallibrary.Subject",
        on_delete=models.PROTECT,
        related_name="configured_exam_papers",
    )

    paper_name = models.CharField(
        max_length=80,
        help_text="Example: Paper 1, Paper 2, Practical or Oral.",
    )

    max_marks = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("1000.00")),
        ],
        help_text=(
            "Maximum marks for this paper. "
            "Examples: 40, 50, 80, 90 or 100."
        ),
    )

    order = models.PositiveSmallIntegerField(
        default=1,
        help_text="The order in which this paper appears.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configured_exam_papers",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "subject__name",
            "order",
            "paper_name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "exam",
                    "subject",
                    "paper_name",
                ],
                name="unique_exam_subject_paper_name",
            ),
            models.CheckConstraint(
                condition=models.Q(max_marks__gt=0),
                name="exam_subject_paper_max_marks_positive",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "exam",
                    "subject",
                    "order",
                ],
                name="exam_subject_paper_lookup_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.exam} - "
            f"{self.subject.name} - "
            f"{self.paper_name} / {self.max_marks}"
        )

    def clean(self):
        super().clean()

        self.paper_name = (self.paper_name or "").strip()

        if not self.paper_name:
            raise ValidationError(
                {
                    "paper_name": (
                        "Enter a name such as Paper 1, "
                        "Paper 2 or Practical."
                    )
                }
            )

        if self.max_marks is None:
            raise ValidationError(
                {
                    "max_marks": (
                        "Enter the maximum marks for this paper."
                    )
                }
            )

        if Decimal(self.max_marks) <= 0:
            raise ValidationError(
                {
                    "max_marks": (
                        "Maximum marks must be greater than zero."
                    )
                }
            )

        if not self.pk:
            return

        previous = (
            ExamSubjectPaper.objects
            .filter(pk=self.pk)
            .values(
                "exam_id",
                "subject_id",
                "paper_name",
                "max_marks",
            )
            .first()
        )

        if not previous:
            return

        changed = (
            previous["exam_id"] != self.exam_id
            or previous["subject_id"] != self.subject_id
            or previous["paper_name"] != self.paper_name
            or Decimal(previous["max_marks"])
            != Decimal(self.max_marks)
        )

        if changed and self.student_marks.exists():
            raise ValidationError(
                "This paper already has pupil marks. Its name, "
                "subject, exam and maximum marks cannot be changed."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class StudentPaperMark(models.Model):
    """
    Stores the raw mark obtained by one pupil in one paper.

    The raw paper marks are combined and converted to a percentage.
    The percentage is then saved in the existing StudentResult model.
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
            MinValueValidator(Decimal("0.00")),
        ],
    )

    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_exam_paper_marks",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "paper__order",
            "paper__paper_name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "student",
                    "paper",
                ],
                name="unique_student_mark_per_exam_paper",
            ),
            models.CheckConstraint(
                condition=models.Q(raw_score__gte=0),
                name="student_paper_mark_nonnegative",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "student",
                    "paper",
                ],
                name="student_paper_mark_lookup_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.paper.paper_name}: "
            f"{self.raw_score}/{self.paper.max_marks}"
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

        raw_score = Decimal(self.raw_score)

        if raw_score < 0:
            raise ValidationError(
                {
                    "raw_score": (
                        "The mark cannot be negative."
                    )
                }
            )

        if self.paper_id:
            maximum = Decimal(self.paper.max_marks)

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
                "This pupil does not belong to the class "
                "assigned to this exam."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
