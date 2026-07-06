# Generated manually to add Director of Studies role choice

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0026_generatedcertificate_only"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("admin", "Administrator"),
                    ("principal", "Principal"),
                    ("deputy_principal", "Deputy Principal"),
                    ("director_of_studies", "Director of Studies"),
                    ("bursar", "Bursar/Accountant"),
                    ("teacher", "Teacher"),
                    ("class_teacher", "Class Teacher"),
                    ("secretary", "Secretary"),
                    ("student", "Student"),
                    ("parent", "Parent"),
                ],
                default="teacher",
            ),
        ),
    ]
