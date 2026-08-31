# Generated repair migration for legacy 8-4-4 / CBE coexistence.

from django.db import migrations
from django.db.models import Q


LEGACY_SUBJECTS = [
    # name, canonical_code, old_legacy_code, category, compulsory, order
    ("English", "ENG", "ENG_LEGACY", "compulsory", True, 10),
    ("Kiswahili", "KIS", "KIS_LEGACY", "compulsory", True, 20),
    ("Mathematics", "MATH_LEGACY", "MATH_LEGACY", "compulsory", True, 30),
    ("Biology", "BIO", "BIO_LEGACY", "stem", False, 40),
    ("Chemistry", "CHEM", "CHEM_LEGACY", "stem", False, 50),
    ("Physics", "PHY", "PHY_LEGACY", "stem", False, 60),
    (
        "History and Government",
        "HIST_GOV",
        "HIST_GOV",
        "social_sciences",
        False,
        70,
    ),
    (
        "Geography",
        "GEO_SOCIAL",
        "GEO_LEGACY",
        "social_sciences",
        False,
        80,
    ),
    (
        "Christian Religious Education",
        "CRE_SOCIAL",
        "CRE_LEGACY",
        "social_sciences",
        False,
        90,
    ),
    (
        "Islamic Religious Education",
        "IRE_SOCIAL",
        "IRE_LEGACY",
        "social_sciences",
        False,
        100,
    ),
    (
        "Business Studies",
        "BUS_SOCIAL",
        "BUS_LEGACY",
        "social_sciences",
        False,
        110,
    ),
    ("Agriculture", "AGR_STEM", "AGR_LEGACY", "stem", False, 120),
    ("Computer Studies", "COMP_LEGACY", "COMP_LEGACY", "stem", False, 130),
]


def _legacy_classes(Class):
    return Class.objects.filter(
        Q(name__iexact="Form 3")
        | Q(name__iexact="Form 4")
        | Q(code__iexact="F3")
        | Q(code__iexact="F4")
        | Q(level="LEGACY_SECONDARY")
        | Q(curriculum="LEGACY_844")
        | Q(is_legacy=True)
    ).distinct()


def repair_legacy_844(apps, schema_editor):
    Class = apps.get_model("digitallibrary", "Class")
    Subject = apps.get_model("digitallibrary", "Subject")

    # 1. Correct existing Form 3 / Form 4 metadata.
    form3 = Class.objects.filter(
        Q(name__iexact="Form 3") | Q(code__iexact="F3")
    )
    form3.update(
        level="LEGACY_SECONDARY",
        curriculum="LEGACY_844",
        requires_pathway=False,
        is_legacy=True,
        sort_order=13,
    )

    form4 = Class.objects.filter(
        Q(name__iexact="Form 4") | Q(code__iexact="F4")
    )
    form4.update(
        level="LEGACY_SECONDARY",
        curriculum="LEGACY_844",
        requires_pathway=False,
        is_legacy=True,
        sort_order=14,
    )

    legacy_classes = list(_legacy_classes(Class))
    if not legacy_classes:
        return

    # 2. Repair / reuse subjects.
    # Shared subjects use a single canonical code across Senior CBE and 8-4-4.
    # Example: Chemistry is CHEM in both curricula and is attached to both
    # class groups. "stem" remains a category only; it does not mean CBE-only.
    for (
        name,
        canonical_code,
        old_legacy_code,
        category,
        is_compulsory,
        order,
    ) in LEGACY_SUBJECTS:
        subject = Subject.objects.filter(
            code=canonical_code
        ).first()

        if subject is None and old_legacy_code:
            subject = Subject.objects.filter(
                code=old_legacy_code
            ).first()

        if subject is None:
            subject = Subject.objects.filter(
                name__iexact=name
            ).first()

        if subject is None:
            subject = Subject.objects.create(
                name=name,
                code=canonical_code,
                category=category,
                is_compulsory=is_compulsory,
                is_active=True,
                order=order,
            )
        else:
            update_fields = []

            # Move old legacy-only codes to the canonical shared code when
            # that code is free. This avoids duplicate Chemistry/Biology/etc.
            if (
                subject.code == old_legacy_code
                and old_legacy_code != canonical_code
                and not Subject.objects.filter(
                    code=canonical_code
                ).exclude(pk=subject.pk).exists()
            ):
                subject.code = canonical_code
                update_fields.append("code")

            if not subject.is_active:
                subject.is_active = True
                update_fields.append("is_active")

            # For the legacy-secondary subjects listed here, these metadata
            # values agree with their Senior equivalents where the subject is
            # shared. Do not infer curriculum from category.
            if subject.category != category:
                subject.category = category
                update_fields.append("category")

            if subject.is_compulsory != is_compulsory:
                subject.is_compulsory = is_compulsory
                update_fields.append("is_compulsory")

            if subject.order != order:
                subject.order = order
                update_fields.append("order")

            if update_fields:
                subject.save(update_fields=update_fields)

        subject.applicable_classes.add(*legacy_classes)


def noop_reverse(apps, schema_editor):
    # Deliberately irreversible data repair. Removing the links on rollback
    # could delete valid subject availability / registrations.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0034_unify_student_result_grading"),
    ]

    operations = [
        migrations.RunPython(
            repair_legacy_844,
            noop_reverse,
        ),
    ]
