# digitallibrary/migrations/0034_unify_student_result_grading.py
from django.db import migrations, models


def populate_grade_metadata(apps, schema_editor):
    StudentResult = apps.get_model("digitallibrary", "StudentResult")

    for result in StudentResult.objects.select_related("grade").iterator():
        label = ""
        system_code = ""

        if result.grade_id and result.grade:
            label = str(getattr(result.grade, "level", "") or "").strip()
            system_code = "cbe"

        if not label:
            remarks = str(result.remarks or "").strip()
            candidate = (
                remarks.split(";", 1)[0]
                .split(" - ", 1)[0]
                .strip()
            )

            if candidate:
                label = candidate
                system_code = (
                    "cbe"
                    if candidate.upper().startswith(
                        ("EE", "ME", "AE", "BE")
                    )
                    else "traditional"
                )

        updates = {}

        if label and not result.grade_label:
            updates["grade_label"] = label

        if system_code and not result.grading_system_used:
            updates["grading_system_used"] = system_code

        if updates:
            StudentResult.objects.filter(pk=result.pk).update(**updates)


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
                    ("traditional", "Traditional Grade System"),
                    ("cbe", "KNEC Competency-Based Education"),
                    ("custom", "Custom Teacher Grading"),
                ],
                db_index=True,
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="studentresult",
            name="teacher_comment",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(
            populate_grade_metadata,
            migrations.RunPython.noop,
        ),
    ]
