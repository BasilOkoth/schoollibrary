from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0029_assignment_resource_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignmentsubmission",
            name="teacher_return_file",
            field=models.FileField(
                upload_to="assignment_returns/%Y/%m/",
                null=True,
                blank=True,
                help_text="Marked, corrected, or returned file uploaded by the teacher.",
            ),
        ),
    ]
