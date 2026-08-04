# digitallibrary/migrations/0034_unify_student_result_grading.py
from django.db import migrations, models


TRADITIONAL_GRADE_LABELS = {
    "A",
    "A-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "C-",
    "D+",
    "D",
    "D-",
    "E",
}

CBE_GRADE_LABELS = {
    "EE1",
    "EE2",
    "ME1",
    "ME2",
    "AE1",
    "AE2",
    "BE1",
    "BE2",
}


def extract_grade_label(remarks):
    """Extract only a recognized grade code from legacy remarks."""

    text = str(remarks or "").strip()

    if not text:
        return "", ""

    candidates = [
        text,
        text.split(";", 1)[0].strip(),
        text.split(" - ", 1)[0].strip(),
        text.split(None, 1)[0].strip("():,;"),
    ]

    for candidate in candidates:
        normalized = candidate.upper()

        if normalized in CBE_GRADE_LABELS:
            return normalized, "cbe"

        if normalized in TRADITIONAL_GRADE_LABELS:
            return normalized, "traditional"

    return "", ""


def populate_grade_metadata(apps, schema_editor):
    """Backfill grade metadata without copying long remark text."""

    StudentResult = apps.get_model(
        "digitallibrary",
        "StudentResult",
    )

    results = StudentResult.objects.select_related("grade").iterator(
        chunk_size=500,
    )

    for result in results:
        label = ""
        system_code = ""

        if result.grade_id and result.grade:
            grade_level = str(
                getattr(result.grade, "level", "") or ""
            ).strip().upper()

            if grade_level in CBE_GRADE_LABELS:
                label = grade_level
                system_code = "cbe"

        if not label:
            label, system_code = extract_grade_label(
                result.remarks,
            )

        updates = {}

        if label and not result.grade_label:
            updates["grade_label"] = label

        if system_code and not result.grading_system_used:
            updates["grading_system_used"] = system_code

        if updates:
            StudentResult.objects.filter(
                pk=result.pk,
            ).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        (
            "digitallibrary",
            "0033_official_senior_subject_combinations",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="studentresult",
            name="grade_label",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="studentresult",
            name="grading_system_used",
            field=models.CharField(
                blank=True,
                choices=[
                    (
                        "traditional",
                        "Traditional Grade System",
                    ),
                    (
                        "cbe",
                        "KNEC Competency-Based Education",
                    ),
                    (
                        "custom",
                        "Custom Teacher Grading",
                    ),
                ],
                db_index=True,
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="studentresult",
            name="teacher_comment",
            field=models.TextField(
                blank=True,
                default="",
            ),
        ),
        migrations.RunPython(
            populate_grade_metadata,
            migrations.RunPython.noop,
        ),
    ]
