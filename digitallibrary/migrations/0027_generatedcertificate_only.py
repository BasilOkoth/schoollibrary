# Generated manually for bulk certificate downloads

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("digitallibrary", "0026_classteacherassignment_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GeneratedCertificate",
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
                    "certificate_file",
                    models.FileField(
                        upload_to="certificates/generated/",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True,
                        max_length=255,
                    ),
                ),
                (
                    "generated_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generated_certificates",
                        to="digitallibrary.exam",
                    ),
                ),
                (
                    "generated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_certificates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="generated_certificates",
                        to="digitallibrary.student",
                    ),
                ),
                (
                    "student_class",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generated_certificates",
                        to="digitallibrary.class",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "student_class__sort_order",
                    "student__last_name",
                    "student__first_name",
                ],
                "unique_together": {("student", "exam")},
            },
        ),
    ]
