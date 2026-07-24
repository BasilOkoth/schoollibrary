from django.db import migrations, models
import django.db.models.deletion


def seed_senior_pathways_and_tracks(apps, schema_editor):
    SeniorPathway = apps.get_model(
        "digitallibrary",
        "SeniorPathway",
    )
    SeniorTrack = apps.get_model(
        "digitallibrary",
        "SeniorTrack",
    )

    pathway_data = [
        {
            "code": "stem",
            "name": "STEM",
            "display_order": 1,
            "tracks": [
                ("pure_sciences", "Pure Sciences", 1),
                ("applied_sciences", "Applied Sciences", 2),
                ("technical_studies", "Technical Studies", 3),
            ],
        },
        {
            "code": "social_sciences",
            "name": "Social Sciences",
            "display_order": 2,
            "tracks": [
                (
                    "languages_literature",
                    "Languages & Literature",
                    1,
                ),
                (
                    "humanities_business",
                    "Humanities & Business Studies",
                    2,
                ),
            ],
        },
        {
            "code": "arts_sports",
            "name": "Arts & Sports Science",
            "display_order": 3,
            "tracks": [
                ("arts", "Arts", 1),
                ("sports", "Sports", 2),
            ],
        },
    ]

    for pathway_item in pathway_data:
        pathway, _created = SeniorPathway.objects.update_or_create(
            code=pathway_item["code"],
            defaults={
                "name": pathway_item["name"],
                "display_order": pathway_item["display_order"],
                "is_active": True,
            },
        )

        for track_code, track_name, display_order in pathway_item[
            "tracks"
        ]:
            SeniorTrack.objects.update_or_create(
                pathway=pathway,
                code=track_code,
                defaults={
                    "name": track_name,
                    "display_order": display_order,
                    "is_active": True,
                },
            )


def keep_seeded_catalogue_on_reverse(apps, schema_editor):
    # Do not delete catalogue records on reverse because schools may already
    # have imported official combinations linked to these pathways/tracks.
    pass


class Migration(migrations.Migration):

    dependencies = [
        (
            "digitallibrary",
            "0032_add_student_mathematics_option",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="SeniorPathway",
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
                        choices=[
                            ("stem", "STEM"),
                            (
                                "social_sciences",
                                "Social Sciences",
                            ),
                            (
                                "arts_sports",
                                "Arts & Sports Science",
                            ),
                        ],
                        db_index=True,
                        max_length=30,
                        unique=True,
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=120),
                ),
                (
                    "description",
                    models.TextField(blank=True),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(default=0),
                ),
            ],
            options={
                "verbose_name": "Senior School Pathway",
                "verbose_name_plural": "Senior School Pathways",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="SeniorTrack",
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
                        db_index=True,
                        help_text=(
                            "Stable ShuleHub track code, "
                            "e.g. pure_sciences."
                        ),
                        max_length=40,
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=120),
                ),
                (
                    "description",
                    models.TextField(blank=True),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                    ),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "pathway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tracks",
                        to="digitallibrary.seniorpathway",
                    ),
                ),
            ],
            options={
                "verbose_name": "Senior School Track",
                "verbose_name_plural": "Senior School Tracks",
                "ordering": [
                    "pathway__display_order",
                    "display_order",
                    "name",
                ],
                "indexes": [
                    models.Index(
                        fields=["pathway", "is_active"],
                        name="sen_track_path_active_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("pathway", "code"),
                        name="uniq_senior_track_code",
                    ),
                    models.UniqueConstraint(
                        fields=("pathway", "name"),
                        name="uniq_senior_track_name",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SeniorSubjectCombination",
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
                        db_index=True,
                        help_text=(
                            "Official Ministry combination code, "
                            "e.g. ST1004."
                        ),
                        max_length=30,
                        unique=True,
                    ),
                ),
                (
                    "official_name",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Display name generated from the "
                            "three official subjects."
                        ),
                        max_length=500,
                    ),
                ),
                (
                    "mathematics_rule",
                    models.CharField(
                        choices=[
                            (
                                "auto",
                                (
                                    "Automatic: Core when listed, "
                                    "otherwise Essential"
                                ),
                            ),
                            ("core", "Core Mathematics"),
                            (
                                "essential",
                                "Essential Mathematics",
                            ),
                        ],
                        default="auto",
                        help_text=(
                            "Normally automatic. A combination "
                            "containing Core Mathematics uses Core; "
                            "other combinations use Essential "
                            "Mathematics."
                        ),
                        max_length=20,
                    ),
                ),
                (
                    "source_url",
                    models.URLField(
                        blank=True,
                        help_text=(
                            "Official Ministry page supporting "
                            "this combination."
                        ),
                    ),
                ),
                (
                    "is_official",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                    ),
                ),
                (
                    "source_checked_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                    ),
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
                    "pathway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subject_combinations",
                        to="digitallibrary.seniorpathway",
                    ),
                ),
                (
                    "track",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subject_combinations",
                        to="digitallibrary.seniortrack",
                    ),
                ),
            ],
            options={
                "verbose_name": (
                    "Official Senior Subject Combination"
                ),
                "verbose_name_plural": (
                    "Official Senior Subject Combinations"
                ),
                "ordering": [
                    "pathway__display_order",
                    "track__display_order",
                    "code",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "pathway",
                            "track",
                            "is_active",
                        ],
                        name="sen_combo_path_track_idx",
                    ),
                    models.Index(
                        fields=[
                            "is_official",
                            "is_active",
                        ],
                        name="sen_combo_off_active_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SeniorCombinationSubject",
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
                    "position",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "Subject 1"),
                            (2, "Subject 2"),
                            (3, "Subject 3"),
                        ],
                    ),
                ),
                (
                    "combination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="combination_subjects",
                        to=(
                            "digitallibrary."
                            "seniorsubjectcombination"
                        ),
                    ),
                ),
                (
                    "subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name=(
                            "senior_combination_positions"
                        ),
                        to="digitallibrary.subject",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "combination__code",
                    "position",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "combination",
                            "position",
                        ],
                        name="sen_combo_subject_pos_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "combination",
                            "subject",
                        ),
                        name="uniq_combo_subject",
                    ),
                    models.UniqueConstraint(
                        fields=(
                            "combination",
                            "position",
                        ),
                        name="uniq_combo_position",
                    ),
                    models.CheckConstraint(
                        condition=(
                            models.Q(position__gte=1)
                            & models.Q(position__lte=3)
                        ),
                        name="combo_position_1_to_3",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="seniorsubjectcombination",
            name="subjects",
            field=models.ManyToManyField(
                related_name="official_senior_combinations",
                through=(
                    "digitallibrary."
                    "SeniorCombinationSubject"
                ),
                to="digitallibrary.subject",
            ),
        ),
        migrations.CreateModel(
            name="ClassSubjectCombination",
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
                    "is_offered",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                    ),
                ),
                (
                    "maximum_students",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True),
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
                    "combination",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="class_offerings",
                        to=(
                            "digitallibrary."
                            "seniorsubjectcombination"
                        ),
                    ),
                ),
                (
                    "school_class",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name=(
                            "offered_subject_combinations"
                        ),
                        to="digitallibrary.class",
                    ),
                ),
            ],
            options={
                "verbose_name": (
                    "Class Subject Combination Offering"
                ),
                "verbose_name_plural": (
                    "Class Subject Combination Offerings"
                ),
                "ordering": [
                    "school_class__sort_order",
                    (
                        "combination__pathway__"
                        "display_order"
                    ),
                    (
                        "combination__track__"
                        "display_order"
                    ),
                    "combination__code",
                ],
                "indexes": [
                    models.Index(
                        fields=[
                            "school_class",
                            "is_offered",
                        ],
                        name="class_combo_offered_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=(
                            "school_class",
                            "combination",
                        ),
                        name="uniq_class_senior_combo",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="student",
            name="subject_combination",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Official Senior School three-subject "
                    "combination. Required for Grade 10–12 "
                    "once the school has configured its "
                    "offerings."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="students",
                to=(
                    "digitallibrary."
                    "seniorsubjectcombination"
                ),
            ),
        ),
        migrations.AddField(
            model_name="studentenrollment",
            name="subject_combination",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Official Senior School subject combination "
                    "for this enrollment."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="student_enrollments",
                to=(
                    "digitallibrary."
                    "seniorsubjectcombination"
                ),
            ),
        ),
        migrations.RunPython(
            seed_senior_pathways_and_tracks,
            keep_seeded_catalogue_on_reverse,
        ),
    ]
