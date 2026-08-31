# digitallibrary/subject_templates.py


PRIMARY_LEARNING_AREAS = [
    ("English", "ENG", "compulsory", True, 10),
    ("Kiswahili", "KIS", "compulsory", True, 20),
    ("Mathematics", "MATH", "compulsory", True, 30),
    ("Environmental Activities", "ENV", "compulsory", True, 40),
    ("Religious Education", "RE", "compulsory", True, 50),
    ("Creative Arts", "CA", "compulsory", True, 60),
    ("Physical and Health Education", "PHE", "compulsory", True, 70),
    ("Agriculture", "AGR", "compulsory", True, 80),
    ("Science and Technology", "SCI_TECH", "compulsory", True, 90),
    ("Social Studies", "SST", "compulsory", True, 100),
]


JUNIOR_LEARNING_AREAS = [
    ("English", "ENG", "compulsory", True, 10),
    ("Kiswahili", "KIS", "compulsory", True, 20),
    ("Mathematics", "MATH", "compulsory", True, 30),
    ("Integrated Science", "INT_SCI", "compulsory", True, 40),
    ("Health Education", "HEALTH", "compulsory", True, 50),
    ("Pre-Technical Studies", "PRE_TECH", "compulsory", True, 60),
    ("Social Studies", "SST", "compulsory", True, 70),
    ("Religious Education", "RE", "compulsory", True, 80),
    ("Business Studies", "BUS", "compulsory", True, 90),
    ("Agriculture", "AGR", "compulsory", True, 100),
    ("Life Skills Education", "LIFE", "compulsory", True, 110),
    ("Sports and Physical Education", "SPE", "compulsory", True, 120),
    ("Visual Arts", "VIS_ART", "arts_sports", False, 130),
    ("Performing Arts", "PERF_ART", "arts_sports", False, 140),
    ("Home Science", "HOME_SCI", "social_sciences", False, 150),
    ("Computer Science", "COMP_SCI", "stem", False, 160),
]


# These are common Senior School learning areas.
# Mathematics is handled separately because a learner must take
# either Core Mathematics or Essential Mathematics, but not both.
SENIOR_COMMON_SUBJECTS = [
    ("English", "ENG", "compulsory", True, 10),
    ("Kiswahili", "KIS", "compulsory", True, 20),
    ("Community Service Learning", "CSL", "compulsory", True, 40),
    ("Physical Education", "PE", "compulsory", True, 50),
]


SENIOR_MATHEMATICS_SUBJECTS = [
    (
        "Core Mathematics",
        "CORE_MATH",
        "stem",
        False,
        30,
    ),
    (
        "Essential Mathematics",
        "ESS_MATH",
        "compulsory",
        False,
        31,
    ),
]


SENIOR_STEM_SUBJECTS = [
    ("Biology", "BIO", "stem", False, 100),
    ("Chemistry", "CHEM", "stem", False, 110),
    ("Physics", "PHY", "stem", False, 120),
    ("General Science", "GEN_SCI", "stem", False, 130),
    ("Computer Science", "COMP_SCI_SENIOR", "stem", False, 140),
    ("Agriculture", "AGR_STEM", "stem", False, 150),
    ("Home Science", "HOME_SCI_STEM", "stem", False, 160),
    ("Aviation Technology", "AVIATION", "stem", False, 170),
    ("Building Construction", "BUILD", "stem", False, 180),
    ("Electricity", "ELECT", "stem", False, 190),
    ("Metalwork", "METAL", "stem", False, 200),
    ("Power Mechanics", "POWER", "stem", False, 210),
    ("Woodwork", "WOOD", "stem", False, 220),
    ("Media Technology", "MEDIA", "stem", False, 230),
]


SENIOR_SOCIAL_SCIENCES_SUBJECTS = [
    (
        "History and Citizenship",
        "HIST_CIT",
        "social_sciences",
        False,
        100,
    ),
    (
        "Geography",
        "GEO_SOCIAL",
        "social_sciences",
        False,
        110,
    ),
    (
        "Christian Religious Education",
        "CRE_SOCIAL",
        "social_sciences",
        False,
        120,
    ),
    (
        "Islamic Religious Education",
        "IRE_SOCIAL",
        "social_sciences",
        False,
        130,
    ),
    (
        "Hindu Religious Education",
        "HRE_SOCIAL",
        "social_sciences",
        False,
        140,
    ),
    (
        "Business Studies",
        "BUS_SOCIAL",
        "social_sciences",
        False,
        150,
    ),
]


SENIOR_ARTS_SPORTS_SUBJECTS = [
    (
        "Sports and Recreation",
        "SPORTS",
        "arts_sports",
        False,
        100,
    ),
    (
        "Physical Education Pathway",
        "PE_ARTS",
        "arts_sports",
        False,
        110,
    ),
    (
        "Music and Dance",
        "MUSIC_DANCE",
        "arts_sports",
        False,
        120,
    ),
    (
        "Theatre and Film",
        "THEATRE_FILM",
        "arts_sports",
        False,
        130,
    ),
    (
        "Fine Arts",
        "FINE_ARTS",
        "arts_sports",
        False,
        140,
    ),
    (
        "Applied Arts",
        "APPLIED_ARTS",
        "arts_sports",
        False,
        150,
    ),
]


# IMPORTANT:
# Subjects that are genuinely the same in CBE Senior and legacy 8-4-4 use
# the SAME canonical subject code. STEM is a category, not a curriculum.
# This means, for example, Chemistry (CHEM) can be attached to both Grade
# 10-12 and Form 3-4 without creating a second "Chemistry" record.
LEGACY_844_SUBJECTS = [
    ("English", "ENG", "compulsory", True, 10),
    ("Kiswahili", "KIS", "compulsory", True, 20),
    ("Mathematics", "MATH_LEGACY", "compulsory", True, 30),
    ("Biology", "BIO", "stem", False, 40),
    ("Chemistry", "CHEM", "stem", False, 50),
    ("Physics", "PHY", "stem", False, 60),
    (
        "History and Government",
        "HIST_GOV",
        "social_sciences",
        False,
        70,
    ),
    (
        "Geography",
        "GEO_SOCIAL",
        "social_sciences",
        False,
        80,
    ),
    (
        "Christian Religious Education",
        "CRE_SOCIAL",
        "social_sciences",
        False,
        90,
    ),
    (
        "Islamic Religious Education",
        "IRE_SOCIAL",
        "social_sciences",
        False,
        100,
    ),
    (
        "Business Studies",
        "BUS_SOCIAL",
        "social_sciences",
        False,
        110,
    ),
    ("Agriculture", "AGR_STEM", "stem", False, 120),
    ("Computer Studies", "COMP_LEGACY", "stem", False, 130),
]


def _get_or_create_subject(
    name,
    code,
    category,
    is_compulsory,
    order,
):
    from digitallibrary.models import Subject

    subject, _created = Subject.objects.update_or_create(
        code=code,
        defaults={
            "name": name,
            "category": category,
            "is_compulsory": is_compulsory,
            "is_active": True,
            "order": order,
        },
    )

    return subject


def _attach_subjects_to_classes(subjects_data, classes):
    classes = list(classes)

    if not classes:
        return

    for (
        name,
        code,
        category,
        is_compulsory,
        order,
    ) in subjects_data:
        subject = _get_or_create_subject(
            name=name,
            code=code,
            category=category,
            is_compulsory=is_compulsory,
            order=order,
        )

        subject.applicable_classes.add(*classes)


def create_default_subjects_for_school_level(school_level):
    """
    Create the appropriate subjects for the classes in the tenant.

    Primary and Junior School:
        Generic Mathematics is used.

    Senior School:
        Generic Mathematics is removed from Grade 10–12.
        Both Core Mathematics and Essential Mathematics are created.
        Each learner later receives exactly one mathematics option.

    Legacy Form 3–4:
        Legacy Mathematics is retained. Subjects that are also present in
        Senior CBE (e.g. Chemistry, Biology and Physics) reuse the same
        canonical Subject record and are attached to the legacy classes too.
    """
    from digitallibrary.models import Class, Subject

    primary_classes = Class.objects.filter(
        level="PRIMARY",
        curriculum="CBC",
    )

    junior_classes = Class.objects.filter(
        level="JUNIOR",
        curriculum="CBC",
    )

    senior_classes = Class.objects.filter(
        level="SENIOR",
        curriculum="CBC",
    )

    legacy_classes = Class.objects.filter(
        level="LEGACY_SECONDARY",
        curriculum="LEGACY_844",
    )

    if primary_classes.exists():
        _attach_subjects_to_classes(
            PRIMARY_LEARNING_AREAS,
            primary_classes,
        )

    if junior_classes.exists():
        _attach_subjects_to_classes(
            JUNIOR_LEARNING_AREAS,
            junior_classes,
        )

    if senior_classes.exists():
        senior_class_list = list(senior_classes)

        # Remove the old generic Mathematics subject from Grade 10–12.
        # It remains available for Primary and Junior classes.
        generic_mathematics = Subject.objects.filter(
            code="MATH",
        ).first()

        if generic_mathematics:
            generic_mathematics.applicable_classes.remove(
                *senior_class_list
            )

            # A Senior-only school no longer needs the old generic subject.
            if not generic_mathematics.applicable_classes.exists():
                generic_mathematics.is_active = False
                generic_mathematics.save(
                    update_fields=["is_active"]
                )

        _attach_subjects_to_classes(
            SENIOR_COMMON_SUBJECTS,
            senior_class_list,
        )

        _attach_subjects_to_classes(
            SENIOR_MATHEMATICS_SUBJECTS,
            senior_class_list,
        )

        _attach_subjects_to_classes(
            SENIOR_STEM_SUBJECTS,
            senior_class_list,
        )

        _attach_subjects_to_classes(
            SENIOR_SOCIAL_SCIENCES_SUBJECTS,
            senior_class_list,
        )

        _attach_subjects_to_classes(
            SENIOR_ARTS_SPORTS_SUBJECTS,
            senior_class_list,
        )

    if legacy_classes.exists():
        _attach_subjects_to_classes(
            LEGACY_844_SUBJECTS,
            legacy_classes,
        )
