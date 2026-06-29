# Generated manually for ShuleHub subscription payment tracking

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0004_schoolsubscriptionaccount"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolSubscriptionPayment",
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
                    "tenant_schema",
                    models.CharField(
                        db_index=True,
                        max_length=100,
                    ),
                ),
                (
                    "requested_by_name",
                    models.CharField(
                        blank=True,
                        max_length=255,
                    ),
                ),
                (
                    "requested_by_email",
                    models.EmailField(
                        blank=True,
                        max_length=254,
                    ),
                ),
                (
                    "phone_number",
                    models.CharField(
                        max_length=30,
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0.00"),
                        max_digits=10,
                    ),
                ),
                (
                    "account_reference",
                    models.CharField(
                        blank=True,
                        max_length=100,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("INITIATED", "Initiated"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "merchant_request_id",
                    models.CharField(
                        blank=True,
                        max_length=255,
                    ),
                ),
                (
                    "checkout_request_id",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=255,
                    ),
                ),
                (
                    "result_code",
                    models.CharField(
                        blank=True,
                        max_length=20,
                    ),
                ),
                (
                    "result_description",
                    models.TextField(
                        blank=True,
                    ),
                ),
                (
                    "mpesa_receipt_number",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=100,
                    ),
                ),
                (
                    "raw_request_response",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "raw_callback",
                    models.JSONField(
                        blank=True,
                        default=dict,
                    ),
                ),
                (
                    "subscription_updated",
                    models.BooleanField(
                        default=False,
                    ),
                ),
                (
                    "updated_subscription_at",
                    models.DateTimeField(
                        blank=True,
                        null=True,
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
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_payments",
                        to="tenants.school",
                    ),
                ),
            ],
            options={
                "verbose_name": "School Subscription Payment",
                "verbose_name_plural": "School Subscription Payments",
                "ordering": ["-created_at"],
            },
        ),
    ]
