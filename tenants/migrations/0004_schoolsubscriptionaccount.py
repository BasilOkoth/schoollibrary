# Generated manually for ShuleHub billing

from decimal import Decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_school_school_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolSubscriptionAccount",
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
                    "plan_name",
                    models.CharField(
                        max_length=100,
                        default="ShuleHub Standard",
                    ),
                ),
                (
                    "payment_model",
                    models.CharField(
                        max_length=30,
                        choices=[
                            ("FIXED", "Fixed Amount per School"),
                            ("PER_STUDENT", "Per Student"),
                            ("CUSTOM", "Custom Negotiated"),
                        ],
                        default="FIXED",
                        help_text="How this school is charged.",
                    ),
                ),
                (
                    "billing_cycle",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("MONTHLY", "Monthly"),
                            ("TERM", "Per Term"),
                            ("YEARLY", "Yearly"),
                            ("CUSTOM", "Custom"),
                        ],
                        default="MONTHLY",
                    ),
                ),
                (
                    "subscription_amount",
                    models.DecimalField(
                        max_digits=10,
                        decimal_places=2,
                        default=Decimal("0.00"),
                        help_text="Fixed subscription amount for the billing cycle.",
                    ),
                ),
                (
                    "amount_per_student",
                    models.DecimalField(
                        max_digits=10,
                        decimal_places=2,
                        default=Decimal("0.00"),
                        help_text="Used only when payment model is Per Student.",
                    ),
                ),
                (
                    "student_count_snapshot",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Used for per-student billing calculation.",
                    ),
                ),
                (
                    "amount_due",
                    models.DecimalField(
                        max_digits=10,
                        decimal_places=2,
                        default=Decimal("0.00"),
                    ),
                ),
                (
                    "next_billing_date",
                    models.DateField(
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "last_paid_date",
                    models.DateField(
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "grace_period_days",
                    models.PositiveIntegerField(default=30),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("ACTIVE", "Active"),
                            ("DUE", "Payment Due"),
                            ("GRACE", "Grace Period"),
                            ("BLOCKED", "Blocked"),
                            ("SUSPENDED", "Suspended"),
                        ],
                        default="ACTIVE",
                    ),
                ),
                (
                    "account_reference",
                    models.CharField(
                        max_length=100,
                        blank=True,
                    ),
                ),
                (
                    "critical_features_blocked",
                    models.BooleanField(default=False),
                ),
                (
                    "auto_calculate_amount_due",
                    models.BooleanField(
                        default=False,
                        help_text="If enabled, amount due can be calculated from payment model.",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "school",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscription_account",
                        to="tenants.school",
                    ),
                ),
            ],
            options={
                "verbose_name": "School Subscription Account",
                "verbose_name_plural": "School Subscription Accounts",
            },
        ),
    ]
