# Generated manually for ShuleHub assignment submission workflow

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0027_add_director_of_studies_role"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add assignment-related fields to existing Resource model
        migrations.AddField(
            model_name="resource",
            name="resource_type",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("notes", "Notes"),
                    ("revision", "Revision Paper"),
                    ("assignment", "Assignment"),
                    ("cat", "CAT"),
                    ("exam", "Exam"),
                ],
                default="notes",
            ),
        ),

        migrations.AddField(
            model_name="resource",
            name="posted_by",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="posted_resources",
            ),
        ),

        migrations.AddField(
            model_name="resource",
            name="assigned_class",
            field=models.ForeignKey(
                to="digitallibrary.class",
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="assigned_resources",
            ),
        ),

        migrations.AddField(
            model_name="resource",
            name="assigned_stream",
            field=models.ForeignKey(
                to="digitallibrary.classstream",
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name="assigned_resources",
            ),
        ),

        migrations.AddField(
            model_name="resource",
            name="allow_submission",
            field=models.BooleanField(default=False),
        ),

        migrations.AddField(
            model_name="resource",
            name="due_date",
            field=models.DateTimeField(
                null=True,
                blank=True,
            ),
        ),

        migrations.AddField(
            model_name="resource",
            name="instructions",
            field=models.TextField(
                blank=True,
                help_text="Instructions for assignments, CATs or exams.",
            ),
        ),

        # Class access code model
        migrations.CreateModel(
            name="ClassAccessCode",
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
                    "code",
                    models.CharField(
                        max_length=80,
                        unique=True,
                        db_index=True,
                    ),
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
                    "created_by",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="created_class_access_codes",
                    ),
                ),
                (
                    "school_class",
                    models.ForeignKey(
                        to="digitallibrary.class",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_codes",
                    ),
                ),
                (
                    "stream",
                    models.ForeignKey(
                        to="digitallibrary.classstream",
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="access_codes",
                    ),
                ),
            ],
            options={
                "verbose_name": "Class Access Code",
                "verbose_name_plural": "Class Access Codes",
                "ordering": [
                    "school_class__name",
                    "stream__name",
                    "code",
                ],
            },
        ),

        # Assignment submission model
        migrations.CreateModel(
            name="AssignmentSubmission",
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
                    "submitted_file",
                    models.FileField(
                        upload_to="assignment_submissions/%Y/%m/",
                    ),
                ),
                (
                    "student_note",
                    models.TextField(blank=True),
                ),
                (
                    "score",
                    models.DecimalField(
                        max_digits=7,
                        decimal_places=2,
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "max_score",
                    models.DecimalField(
                        max_digits=7,
                        decimal_places=2,
                        default=100,
                    ),
                ),
                (
                    "teacher_comment",
                    models.TextField(blank=True),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=30,
                        choices=[
                            ("submitted", "Submitted"),
                            ("marked", "Marked"),
                            ("returned", "Returned"),
                            ("resubmit", "Needs Resubmission"),
                        ],
                        default="submitted",
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "marked_at",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        to="digitallibrary.resource",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_submissions",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        to="digitallibrary.student",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_submissions",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL,
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="received_assignment_submissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "Assignment Submission",
                "verbose_name_plural": "Assignment Submissions",
                "ordering": ["-submitted_at"],
                "unique_together": {("resource", "student")},
            },
        ),
    ]
