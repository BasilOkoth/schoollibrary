from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "digitallibrary",
            "0031_REPLACE_WITH_THE_COMPLETE_EXISTING_NAME",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="mathematics_option",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("core", "Core Mathematics"),
                    ("essential", "Essential Mathematics"),
                ],
                blank=True,
                default="",
                db_index=True,
                help_text=(
                    "Required for Grade 10–12. Select either "
                    "Core Mathematics or Essential Mathematics. "
                    "Leave blank for Grade 1–9 and legacy Form 3–4."
                ),
            ),
        ),
    ]
