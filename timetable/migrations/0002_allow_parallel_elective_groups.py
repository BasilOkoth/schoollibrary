# File: timetable/migrations/0002_allow_parallel_elective_groups.py

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0036_allow_parallel_elective_groups"),
        ("timetable", "0001_initial"),
    ]

    operations = [
        # stream_id already exists in PostgreSQL, but Django migration
        # state from 0001 does not know about it.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="timetableentry",
                    name="stream",
                    field=models.ForeignKey(
                        blank=True,
                        help_text=(
                            "Optional. Select a stream such as East, West, North. "
                            "Leave blank if this lesson applies to the whole class."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="timetable_entries",
                        to="digitallibrary.classstream",
                    ),
                ),
                migrations.AlterUniqueTogether(
                    name="timetableentry",
                    unique_together=set(),
                ),
            ],
        ),

        # lesson_group does not yet exist in PostgreSQL, so this must
        # update both Django state and the real database.
        migrations.AddField(
            model_name="timetableentry",
            name="lesson_group",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Optional. Use this when only part of the class or stream "
                    "takes this lesson, for example 'Business option', "
                    "'Agriculture option', or 'Physics group'. "
                    "Leave blank for the normal class/stream lesson."
                ),
                max_length=100,
            ),
        ),

        migrations.AlterModelOptions(
            name="timetableentry",
            options={
                "ordering": [
                    "day__sort_order",
                    "period__sort_order",
                    "class_group__sort_order",
                    "class_group__name",
                    "stream__name",
                    "lesson_group",
                ],
            },
        ),

        # The current uniqueness rules exist as PostgreSQL UNIQUE INDEXES,
        # not pg_constraint table constraints.
        migrations.RunSQL(
            sql=(
                'DROP INDEX IF EXISTS '
                '"unique_active_whole_class_timetable_entry";'
            ),
            reverse_sql="""
                CREATE UNIQUE INDEX
                    "unique_active_whole_class_timetable_entry"
                ON "timetable_timetableentry"
                    (
                        "template_id",
                        "day_id",
                        "period_id",
                        "class_group_id"
                    )
                WHERE "is_active"
                  AND "stream_id" IS NULL;
            """,
        ),

        migrations.RunSQL(
            sql=(
                'DROP INDEX IF EXISTS '
                '"unique_active_stream_timetable_entry";'
            ),
            reverse_sql="""
                CREATE UNIQUE INDEX
                    "unique_active_stream_timetable_entry"
                ON "timetable_timetableentry"
                    (
                        "template_id",
                        "day_id",
                        "period_id",
                        "class_group_id",
                        "stream_id"
                    )
                WHERE "is_active"
                  AND "stream_id" IS NOT NULL;
            """,
        ),

        # One normal/default lesson for the whole class.
        migrations.AddConstraint(
            model_name="timetableentry",
            constraint=models.UniqueConstraint(
                fields=(
                    "template",
                    "day",
                    "period",
                    "class_group",
                ),
                condition=models.Q(
                    is_active=True,
                    lesson_group="",
                    stream__isnull=True,
                ),
                name="unique_active_whole_class_timetable_entry",
                violation_error_message=(
                    "This class already has a default whole-class lesson "
                    "at this time."
                ),
            ),
        ),

        # One normal/default lesson for a stream.
        migrations.AddConstraint(
            model_name="timetableentry",
            constraint=models.UniqueConstraint(
                fields=(
                    "template",
                    "day",
                    "period",
                    "class_group",
                    "stream",
                ),
                condition=models.Q(
                    is_active=True,
                    lesson_group="",
                    stream__isnull=False,
                ),
                name="unique_active_stream_timetable_entry",
                violation_error_message=(
                    "This stream already has a default lesson at this time."
                ),
            ),
        ),

        # Parallel whole-class elective groups are allowed, but the same
        # named group cannot be scheduled twice in the same period.
        migrations.AddConstraint(
            model_name="timetableentry",
            constraint=models.UniqueConstraint(
                fields=(
                    "template",
                    "day",
                    "period",
                    "class_group",
                    "lesson_group",
                ),
                condition=(
                    models.Q(
                        is_active=True,
                        stream__isnull=True,
                    )
                    & ~models.Q(lesson_group="")
                ),
                name="unique_active_class_lesson_group_entry",
                violation_error_message=(
                    "This lesson group already has another lesson "
                    "at this time."
                ),
            ),
        ),

        # Parallel stream elective groups are allowed, but the same
        # named group cannot be scheduled twice in the same period.
        migrations.AddConstraint(
            model_name="timetableentry",
            constraint=models.UniqueConstraint(
                fields=(
                    "template",
                    "day",
                    "period",
                    "class_group",
                    "stream",
                    "lesson_group",
                ),
                condition=(
                    models.Q(
                        is_active=True,
                        stream__isnull=False,
                    )
                    & ~models.Q(lesson_group="")
                ),
                name="unique_active_stream_lesson_group_entry",
                violation_error_message=(
                    "This lesson group already has another lesson "
                    "for this stream at this time."
                ),
            ),
        ),
    ]
