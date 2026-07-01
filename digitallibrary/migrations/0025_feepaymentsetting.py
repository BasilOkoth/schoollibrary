from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("digitallibrary", "0024_repair_student_promotion_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeePaymentSetting",
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
                    "business_name",
                    models.CharField(
                        blank=True,
                        max_length=150,
                    ),
                ),
                (
                    "paybill_number",
                    models.CharField(
                        blank=True,
                        max_length=30,
                    ),
                ),
                (
                    "account_reference_format",
                    models.CharField(
                        blank=True,
                        default="Use the student admission number as the account number.",
                        max_length=255,
                    ),
                ),
                (
                    "parent_payment_notes",
                    models.TextField(
                        blank=True,
                    ),
                ),
                (
                    "payment_prompt_enabled",
                    models.BooleanField(
                        default=True,
                    ),
                ),
                (
                    "auto_update_enabled",
                    models.BooleanField(
                        default=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_fee_payment_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Fee Payment Setting",
                "verbose_name_plural": "Fee Payment Settings",
            },
        ),
    ]
