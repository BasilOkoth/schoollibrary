CLASS_TEMPLATES = {
    "PRIMARY": [
        ("Grade 1", "G1", "PRIMARY", "CBC", 1, False, False),
        ("Grade 2", "G2", "PRIMARY", "CBC", 2, False, False),
        ("Grade 3", "G3", "PRIMARY", "CBC", 3, False, False),
        ("Grade 4", "G4", "PRIMARY", "CBC", 4, False, False),
        ("Grade 5", "G5", "PRIMARY", "CBC", 5, False, False),
        ("Grade 6", "G6", "PRIMARY", "CBC", 6, False, False),
    ],
    "JUNIOR": [
        ("Grade 7", "G7", "JUNIOR", "CBC", 7, False, False),
        ("Grade 8", "G8", "JUNIOR", "CBC", 8, False, False),
        ("Grade 9", "G9", "JUNIOR", "CBC", 9, False, False),
    ],
    "SENIOR": [
        ("Grade 10", "G10", "SENIOR", "CBC", 10, True, False),
        ("Grade 11", "G11", "SENIOR", "CBC", 11, True, False),
        ("Grade 12", "G12", "SENIOR", "CBC", 12, True, False),
    ],
    "LEGACY_SECONDARY": [
        ("Form 3", "F3", "LEGACY_SECONDARY", "LEGACY_844", 13, False, True),
        ("Form 4", "F4", "LEGACY_SECONDARY", "LEGACY_844", 14, False, True),
    ],
}


SCHOOL_LEVEL_CLASS_GROUPS = {
    "PRIMARY": ["PRIMARY"],
    "JUNIOR": ["JUNIOR"],
    "SENIOR": ["SENIOR"],
    "PRIMARY_JUNIOR": ["PRIMARY", "JUNIOR"],
    "JUNIOR_SENIOR": ["JUNIOR", "SENIOR"],
    "COMPREHENSIVE": ["PRIMARY", "JUNIOR", "SENIOR"],
    "CBC_LEGACY_SECONDARY": ["SENIOR", "LEGACY_SECONDARY"],
    "LEGACY_SECONDARY": ["LEGACY_SECONDARY"],
}


def get_class_templates_for_school_level(school_level):
    groups = SCHOOL_LEVEL_CLASS_GROUPS.get(
        school_level,
        ["SENIOR", "LEGACY_SECONDARY"],
    )

    classes = []

    for group in groups:
        classes.extend(CLASS_TEMPLATES.get(group, []))

    return classes


def create_default_classes_for_school_level(school_level):
    from digitallibrary.models import Class

    for (
        name,
        code,
        level,
        curriculum,
        sort_order,
        requires_pathway,
        is_legacy,
    ) in get_class_templates_for_school_level(school_level):
        Class.objects.update_or_create(
            name=name,
            defaults={
                "code": code,
                "level": level,
                "curriculum": curriculum,
                "sort_order": sort_order,
                "requires_pathway": requires_pathway,
                "is_legacy": is_legacy,
            },
        )
