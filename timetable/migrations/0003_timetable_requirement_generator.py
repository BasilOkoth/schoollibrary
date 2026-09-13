# File: timetable/migrations/0003_timetable_requirement_generator.py

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("digitallibrary", "0022_classstream_student_stream"),
        ("timetable", "0002_allow_parallel_elective_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="TimetableRequirement",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "apply_to_all_streams",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Create this weekly requirement separately for every "
                            "active stream in the selected class."
                        ),
                    ),
                ),
                (
                    "lessons_per_week",
                    models.PositiveSmallIntegerField(
                        default=4,
                        help_text="Total teaching periods required each week.",
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(20),
                        ],
                    ),
                ),
                (
                    "consecutive_periods",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Single period"),
                            (2, "Double period"),
                        ],
                        default=1,
                        help_text=(
                            "Choose Double period when every session must use "
                            "two adjacent teaching periods."
                        ),
                    ),
                ),
                (
                    "lesson_group",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Optional learner group, e.g. Business option. "
                            "Parallel subjects must use different lesson-group "
                            "names."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "parallel_block",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "Give subjects that must run at the same time the "
                            "same block name, e.g. FORM3_OPTIONS."
                        ),
                        max_length=100,
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "class_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timetable_requirements",
                        to="digitallibrary.class",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_timetable_requirements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="timetable_requirements",
                        to="timetable.timetableroom",
                    ),
                ),
                (
                    "stream",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timetable_requirements",
                        to="digitallibrary.classstream",
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timetable_requirements",
                        to="digitallibrary.subject",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="timetable_requirements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="requirements",
                        to="timetable.timetabletemplate",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "class_group__sort_order",
                    "class_group__name",
                    "stream__name",
                    "parallel_block",
                    "subject__name",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "template",
                            "class_group",
                            "stream",
                            "is_active",
                        ],
                        name="tt_req_scope_active_idx",
                    ),
                    models.Index(
                        fields=[
                            "template",
                            "parallel_block",
                            "is_active",
                        ],
                        name="tt_req_parallel_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="TimetableGenerationDraft",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "proposals",
                    models.JSONField(default=list),
                ),
                (
                    "errors",
                    models.JSONField(default=list),
                ),
                (
                    "warnings",
                    models.JSONField(default=list),
                ),
                (
                    "is_applied",
                    models.BooleanField(default=False),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timetable_generation_drafts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generation_drafts",
                        to="timetable.timetabletemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=[
                            "template",
                            "created_by",
                            "is_applied",
                        ],
                        name="tt_draft_owner_idx",
                    ),
                ],
            },
        ),
    ]
