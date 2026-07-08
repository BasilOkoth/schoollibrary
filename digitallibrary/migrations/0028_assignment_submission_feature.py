# Generated manually for ShuleHub assignment submission workflow
# Safe version for tenants where some Resource columns already exist.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0027_add_director_of_studies_role"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ============================================================
        # RESOURCE ASSIGNMENT FIELDS
        # ============================================================
        # These use ADD COLUMN IF NOT EXISTS because some tenants may
        # already have the columns from a previous/manual attempt.
        # ============================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS resource_type varchar(30) NOT NULL DEFAULT 'notes';
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS resource_type;
                    """,
                ),
            ],
            state_operations=[
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
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS posted_by_id integer;
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS posted_by_id;
                    """,
                ),
            ],
            state_operations=[
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
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS assigned_class_id bigint;
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS assigned_class_id;
                    """,
                ),
            ],
            state_operations=[
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
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS assigned_stream_id bigint;
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS assigned_stream_id;
                    """,
                ),
            ],
            state_operations=[
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
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS allow_submission boolean NOT NULL DEFAULT false;
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS allow_submission;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="resource",
                    name="allow_submission",
                    field=models.BooleanField(default=False),
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS due_date timestamp with time zone;
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS due_date;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="resource",
                    name="due_date",
                    field=models.DateTimeField(
                        null=True,
                        blank=True,
                    ),
                ),
            ],
        ),

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE digitallibrary_resource
                        ADD COLUMN IF NOT EXISTS instructions text NOT NULL DEFAULT '';
                    """,
                    reverse_sql="""
                        ALTER TABLE digitallibrary_resource
                        DROP COLUMN IF EXISTS instructions;
                    """,
                ),
            ],
            state_operations=[
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

        # ============================================================
        # CLASS ACCESS CODE MODEL
        # ============================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
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
                    reverse_sql="""
                        DROP TABLE IF EXISTS digitallibrary_classaccesscode CASCADE;
                    """,
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
            ],
        ),

        # ============================================================
        # ASSIGNMENT SUBMISSION MODEL
        # ============================================================

        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
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
                    reverse_sql="""
                        DROP TABLE IF EXISTS digitallibrary_assignmentsubmission CASCADE;
                    """,
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
            ],
        ),

        # ============================================================
        # OPTIONAL INDEXES
        # ============================================================

        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS digitallibrary_resource_resource_type_idx
                ON digitallibrary_resource (resource_type);

                CREATE INDEX IF NOT EXISTS digitallibrary_resource_assigned_class_idx
                ON digitallibrary_resource (assigned_class_id);

                CREATE INDEX IF NOT EXISTS digitallibrary_resource_assigned_stream_idx
                ON digitallibrary_resource (assigned_stream_id);

                CREATE INDEX IF NOT EXISTS digitallibrary_classaccesscode_code_idx
                ON digitallibrary_classaccesscode (code);

                CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_resource_idx
                ON digitallibrary_assignmentsubmission (resource_id);

                CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_student_idx
                ON digitallibrary_assignmentsubmission (student_id);

                CREATE INDEX IF NOT EXISTS digitallibrary_assignmentsubmission_teacher_idx
                ON digitallibrary_assignmentsubmission (teacher_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS digitallibrary_resource_resource_type_idx;
                DROP INDEX IF EXISTS digitallibrary_resource_assigned_class_idx;
                DROP INDEX IF EXISTS digitallibrary_resource_assigned_stream_idx;
                DROP INDEX IF EXISTS digitallibrary_classaccesscode_code_idx;
                DROP INDEX IF EXISTS digitallibrary_assignmentsubmission_resource_idx;
                DROP INDEX IF EXISTS digitallibrary_assignmentsubmission_student_idx;
                DROP INDEX IF EXISTS digitallibrary_assignmentsubmission_teacher_idx;
            """,
        ),
    ]
