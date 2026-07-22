from decimal import Decimal

import django.core.validators
import django.db.models.deletion

from django.conf import settings
from django.db import (
    migrations,
    models,
)


def create_overall_components(
    apps,
    schema_editor,
):
    Component = apps.get_model(
        "exampapers",
        "ExamSubjectComponent",
    )

    Paper = apps.get_model(
        "exampapers",
        "ExamSubjectPaper",
    )

    pairs = (
        Paper.objects
        .values(
            "exam_id",
            "subject_id",
        )
        .distinct()
    )

    for pair in pairs:
        component, _created = (
            Component.objects
            .get_or_create(
                exam_id=pair[
                    "exam_id"
                ],
                subject_id=pair[
                    "subject_id"
                ],
                name="Overall",
                defaults={
                    "weight_percentage": (
                        Decimal("100.00")
                    ),
                    "order": 1,
                },
            )
        )

        (
            Paper.objects
            .filter(
                exam_id=pair[
                    "exam_id"
                ],
                subject_id=pair[
                    "subject_id"
                ],
            )
            .update(
                component_id=(
                    component.id
                )
            )
        )


def restore_old_fields(
    apps,
    schema_editor,
):
    Paper = apps.get_model(
        "exampapers",
        "ExamSubjectPaper",
    )

    for paper in (
        Paper.objects
        .select_related(
            "component"
        )
        .all()
    ):
        paper.exam_id = (
            paper.component.exam_id
        )

        paper.subject_id = (
            paper.component.subject_id
        )

        paper.save(
            update_fields=[
                "exam",
                "subject",
            ]
        )


class Migration(
    migrations.Migration
):

    dependencies = [
        (
            "exampapers",
            "0001_initial",
        ),
        migrations.swappable_dependency(
            settings.AUTH_USER_MODEL
        ),
    ]

    operations = [
        migrations.CreateModel(
            name=(
                "ExamSubjectComponent"
            ),
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
                    "name",
                    models.CharField(
                        max_length=80,
                        help_text=(
                            "Examples: Theory, "
                            "Practical, Oral, "
                            "Project or Overall."
                        ),
                    ),
                ),
                (
                    "weight_percentage",
                    models.DecimalField(
                        max_digits=5,
                        decimal_places=2,
                        validators=[
                            (
                                django
                                .core
                                .validators
                                .MinValueValidator(
                                    Decimal(
                                        "0.01"
                                    )
                                )
                            ),
                            (
                                django
                                .core
                                .validators
                                .MaxValueValidator(
                                    Decimal(
                                        "100.00"
                                    )
                                )
                            ),
                        ],
                    ),
                ),
                (
                    "order",
                    models
                    .PositiveSmallIntegerField(
                        default=1
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=(
                            django
                            .db
                            .models
                            .deletion
                            .SET_NULL
                        ),
                        related_name=(
                            "configured_"
                            "exam_components"
                        ),
                        to=(
                            settings
                            .AUTH_USER_MODEL
                        ),
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=(
                            django
                            .db
                            .models
                            .deletion
                            .CASCADE
                        ),
                        related_name=(
                            "subject_components"
                        ),
                        to=(
                            "digitallibrary.exam"
                        ),
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=(
                            django
                            .db
                            .models
                            .deletion
                            .PROTECT
                        ),
                        related_name=(
                            "exam_components"
                        ),
                        to=(
                            "digitallibrary."
                            "subject"
                        ),
                    ),
                ),
            ],
            options={
                "ordering": [
                    "subject__name",
                    "order",
                    "name",
                ],
            },
        ),

        migrations.AddConstraint(
            model_name=(
                "examsubjectcomponent"
            ),
            constraint=(
                models.UniqueConstraint(
                    fields=(
                        "exam",
                        "subject",
                        "name",
                    ),
                    name=(
                        "unique_exam_"
                        "subject_component"
                    ),
                )
            ),
        ),

        migrations.AddConstraint(
            model_name=(
                "examsubjectcomponent"
            ),
            constraint=(
                models.CheckConstraint(
                    condition=(
                        models.Q(
                            weight_percentage__gt=0
                        )
                        & models.Q(
                            weight_percentage__lte=100
                        )
                    ),
                    name=(
                        "exam_component_"
                        "weight_valid"
                    ),
                )
            ),
        ),

        migrations.AddIndex(
            model_name=(
                "examsubjectcomponent"
            ),
            index=models.Index(
                fields=[
                    "exam",
                    "subject",
                    "order",
                ],
                name=(
                    "exam_subject_"
                    "component_idx"
                ),
            ),
        ),

        migrations.AddField(
            model_name=(
                "examsubjectpaper"
            ),
            name="component",
            field=models.ForeignKey(
                null=True,
                on_delete=(
                    django
                    .db
                    .models
                    .deletion
                    .CASCADE
                ),
                related_name="papers",
                to=(
                    "exampapers."
                    "examsubjectcomponent"
                ),
            ),
        ),

        migrations.RunPython(
            create_overall_components,
            restore_old_fields,
        ),

        migrations.RemoveConstraint(
            model_name=(
                "examsubjectpaper"
            ),
            name=(
                "unique_exam_"
                "subject_paper_name"
            ),
        ),

        migrations.RemoveIndex(
            model_name=(
                "examsubjectpaper"
            ),
            name=(
                "exam_subject_"
                "paper_lookup_idx"
            ),
        ),

        migrations.RemoveField(
            model_name=(
                "examsubjectpaper"
            ),
            name="exam",
        ),

        migrations.RemoveField(
            model_name=(
                "examsubjectpaper"
            ),
            name="subject",
        ),

        migrations.AlterField(
            model_name=(
                "examsubjectpaper"
            ),
            name="component",
            field=models.ForeignKey(
                on_delete=(
                    django
                    .db
                    .models
                    .deletion
                    .CASCADE
                ),
                related_name="papers",
                to=(
                    "exampapers."
                    "examsubjectcomponent"
                ),
            ),
        ),

        migrations.AlterModelOptions(
            name=(
                "examsubjectpaper"
            ),
            options={
                "ordering": [
                    "component__order",
                    "order",
                    "paper_name",
                ],
            },
        ),

        migrations.AlterModelOptions(
            name=(
                "studentpapermark"
            ),
            options={
                "ordering": [
                    (
                        "paper__component__"
                        "order"
                    ),
                    "paper__order",
                    "paper__paper_name",
                ],
            },
        ),

        migrations.AddConstraint(
            model_name=(
                "examsubjectpaper"
            ),
            constraint=(
                models.UniqueConstraint(
                    fields=(
                        "component",
                        "paper_name",
                    ),
                    name=(
                        "unique_component_"
                        "paper_name"
                    ),
                )
            ),
        ),

        migrations.AddIndex(
            model_name=(
                "examsubjectpaper"
            ),
            index=models.Index(
                fields=[
                    "component",
                    "order",
                ],
                name=(
                    "component_paper_"
                    "lookup_idx"
                ),
            ),
        ),
    ]
