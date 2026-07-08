# Generated manually for ShuleHub assignment workflow
# digitallibrary/migrations/0029_assignment_resource_fields.py

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0028_assignment_submission_feature"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------
        # RESOURCE: database-safe SQL
        # ------------------------------------------------------------
        migrations.RunSQL(
            sql=[
                # file_type is the old PDF / Word / Video / Other meaning.
                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS file_type varchar(20) NOT NULL DEFAULT 'PDF';
                """,

                # Copy old resource_type values to file_type before changing resource_type meaning.
                """
                UPDATE digitallibrary_resource
                SET file_type = resource_type
                WHERE resource_type IN ('PDF', 'DOC', 'VIDEO', 'OTHER')
                  AND (file_type IS NULL OR file_type = '' OR file_type = 'PDF');
                """,

                # resource_type now means Notes / Revision / Assignment / CAT / Exam.
                """
                ALTER TABLE digitallibrary_resource
                ALTER COLUMN resource_type TYPE varchar(30);
                """,

                """
                ALTER TABLE digitallibrary_resource
                ALTER COLUMN resource_type SET DEFAULT 'notes';
                """,

                # Convert old file-format values into learning item type.
                """
                UPDATE digitallibrary_resource
                SET resource_type = 'notes'
                WHERE resource_type IN ('PDF', 'DOC', 'VIDEO', 'OTHER')
                   OR resource_type IS NULL
                   OR resource_type = '';
                """,

                """
                ALTER TABLE digitallibrary_resource
                ALTER COLUMN resource_type SET NOT NULL;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS posted_by_id integer NULL;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS assigned_class_id bigint NULL;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS assigned_stream_id bigint NULL;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS allow_submission boolean NOT NULL DEFAULT false;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS due_date timestamp with time zone NULL;
                """,

                """
                ALTER TABLE digitallibrary_resource
                ADD COLUMN IF NOT EXISTS instructions text NOT NULL DEFAULT '';
                """,

                """
                CREATE INDEX IF NOT EXISTS digitallibrary_resource_resource_type_idx
                ON digitallibrary_resource (resource_type);
                """,

                """
                CREATE INDEX IF NOT EXISTS digitallibrary_resource_file_type_idx
                ON digitallibrary_resource (file_type);
                """,

                """
                CREATE INDEX IF NOT EXISTS digitallibrary_resource_assigned_class_idx
                ON digitallibrary_resource (assigned_class_id);
                """,

                """
                CREATE INDEX IF NOT EXISTS digitallibrary_resource_assigned_stream_idx
                ON digitallibrary_resource (assigned_stream_id);
                """,
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),

        # ------------------------------------------------------------
        # RESOURCE: Django state only
        # These tell Django the model has these fields without trying
        # to recreate columns that may already exist.
        # ------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
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
                        help_text="Choose whether this resource is notes, revision, assignment, CAT or exam.",
                    ),
                ),
                migrations.AddField(
                    model_name="resource",
                    name="file_type",
                    field=models.CharField(
                        max_length=20,
                        choices=[
                            ("PDF", "PDF"),
                            ("DOC", "Word Document"),
                            ("VIDEO", "Video"),
                            ("OTHER", "Other"),
                        ],
                        default="PDF",
                        help_text="Actual file format uploaded.",
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
                    field=models.DateTimeField(null=True, blank=True),
                ),
                migrations.AddField(
                    model_name="resource",
                    name="instructions",
                    field=models.TextField(
                        blank=True,
                        help_text="Instructions for assignments, CATs or exams.",
                    ),
                ),
            ],
        ),

        # ------------------------------------------------------------
        # CLASS ACCESS CODE TABLE
        # Safe even if created earlier.
        # ------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        """
                        CREATE TABLE IF NOT EXISTS digitallibrary_classaccesscode (
                            id bigserial PRIMARY KEY,
                            code varchar(80) NOT NULL UNIQUE,
                            is_active boolean NOT NULL DEFAULT true,
                            created_at timestamp with time zone NOT NULL DEFAULT NOW(),
                            created_by_id integer NULL,
                            school_class_id bigint NOT NULL,
                            stream_id bigint NULL
                        );
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_classaccesscode_school_class_idx
                        ON digitallibrary_classaccesscode (school_class_id);
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_classaccesscode_stream_idx
                        ON digitallibrary_classaccesscode (stream_id);
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_classaccesscode_code_idx
                        ON digitallibrary_classaccesscode (code);
                        """,
                    ],
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
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
                        ("code", models.CharField(max_length=80, unique=True)),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
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
                                on_delete=django.db.models.deletion.CASCADE,
                                null=True,
                                blank=True,
                                related_name="access_codes",
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["school_class__sort_order", "school_class__name", "stream__name"],
                    },
                ),
            ],
        ),

        # ------------------------------------------------------------
        # ASSIGNMENT SUBMISSION TABLE
        # Safe even if created earlier.
        # ------------------------------------------------------------
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        """
                        CREATE TABLE IF NOT EXISTS digitallibrary_assignmentsubmission (
                            id bigserial PRIMARY KEY,
                            submitted_file varchar(100) NOT NULL,
                            student_note text NOT NULL DEFAULT '',
                            score numeric(7, 2) NULL,
                            max_score numeric(7, 2) NOT NULL DEFAULT 100,
                            teacher_comment text NOT NULL DEFAULT '',
                            status varchar(30) NOT NULL DEFAULT 'submitted',
                            submitted_at timestamp with time zone NOT NULL DEFAULT NOW(),
                            marked_at timestamp with time zone NULL,
                            resource_id bigint NOT NULL,
                            student_id bigint NOT NULL,
                            teacher_id integer NULL,
                            UNIQUE (resource_id, student_id)
                        );
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_resource_idx
                        ON digitallibrary_assignmentsubmission (resource_id);
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_student_idx
                        ON digitallibrary_assignmentsubmission (student_id);
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_teacher_idx
                        ON digitallibrary_assignmentsubmission (teacher_id);
                        """,
                        """
                        CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_status_idx
                        ON digitallibrary_assignmentsubmission (status);
                        """,
                    ],
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
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
                            models.FileField(upload_to="assignment_submissions/%Y/%m/%d/"),
                        ),
                        ("student_note", models.TextField(blank=True)),
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
                        ("teacher_comment", models.TextField(blank=True)),
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
                        ("submitted_at", models.DateTimeField(auto_now_add=True)),
                        ("marked_at", models.DateTimeField(null=True, blank=True)),
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
                        "ordering": ["-submitted_at"],
                        "unique_together": {("resource", "student")},
                    },
                ),
            ],
        ),
    ]
