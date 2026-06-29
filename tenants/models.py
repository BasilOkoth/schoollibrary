# tenants/models.py

from django.db import models, connection
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin, DomainMixin

SCHOOL_LEVEL_CHOICES = [
    ("PRIMARY", "Primary School"),
    ("JUNIOR", "Junior School"),
    ("SENIOR", "Senior School"),
    ("PRIMARY_JUNIOR", "Primary + Junior School"),
    ("JUNIOR_SENIOR", "Junior + Senior School"),
    ("COMPREHENSIVE", "Comprehensive School"),
    ("CBC_LEGACY_SECONDARY", "CBC + Legacy Secondary School"),
    ("LEGACY_SECONDARY", "Legacy Secondary School"),
]


class School(TenantMixin):
    """School/Tenant model for multi-tenant setup"""
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    created_on = models.DateField(auto_now_add=True)

    school_level = models.CharField(
        max_length=30,
        choices=SCHOOL_LEVEL_CHOICES,
        default="CBC_LEGACY_SECONDARY",
        help_text=(
            "Defines the school structure: Primary, Junior, Senior, "
            "Comprehensive, or CBC + Legacy Secondary."
        ),
    )
    # Subscription fields
    paid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Subscription paid until date"
    )
    on_trial = models.BooleanField(
        default=True,
        help_text="Whether the school is on trial period"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the school is active"
    )

    # Auto-create tenant schema when saving.
    # Because this is True, do not manually run migrate_schemas again
    # inside create_tenant().
    auto_create_schema = True

    def __str__(self):
        return self.name

from decimal import Decimal
from django.db import models
from django.utils import timezone

from decimal import Decimal
from datetime import timedelta

from django.db import models
from django.utils import timezone


PAYMENT_MODEL_CHOICES = [
    ("FIXED", "Fixed Amount per School"),
    ("PER_STUDENT", "Per Student"),
    ("CUSTOM", "Custom Negotiated"),
]

SUBSCRIPTION_STATUS_CHOICES = [
    ("ACTIVE", "Active"),
    ("DUE", "Payment Due"),
    ("GRACE", "Grace Period"),
    ("BLOCKED", "Blocked"),
    ("SUSPENDED", "Suspended"),
]

SUBSCRIPTION_BILLING_CYCLE_CHOICES = [
    ("MONTHLY", "Monthly"),
    ("TERM", "Per Term"),
    ("YEARLY", "Yearly"),
    ("CUSTOM", "Custom"),
]


class SchoolSubscriptionAccount(models.Model):
    school = models.OneToOneField(
        School,
        on_delete=models.CASCADE,
        related_name="subscription_account",
    )

    plan_name = models.CharField(max_length=100, default="ShuleHub Standard")

    payment_model = models.CharField(
        max_length=30,
        choices=PAYMENT_MODEL_CHOICES,
        default="FIXED",
        help_text="How this school is charged.",
    )

    billing_cycle = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_BILLING_CYCLE_CHOICES,
        default="MONTHLY",
    )

    subscription_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Fixed subscription amount for the billing cycle.",
    )

    amount_per_student = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Used only when payment model is Per Student.",
    )

    student_count_snapshot = models.PositiveIntegerField(
        default=0,
        help_text="Used for per-student billing calculation.",
    )

    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    next_billing_date = models.DateField(null=True, blank=True)
    last_paid_date = models.DateField(null=True, blank=True)

    grace_period_days = models.PositiveIntegerField(default=30)

    status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default="ACTIVE",
    )

    account_reference = models.CharField(max_length=100, blank=True)

    critical_features_blocked = models.BooleanField(default=False)

    auto_calculate_amount_due = models.BooleanField(
        default=False,
        help_text="If enabled, amount due can be calculated from payment model.",
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def expected_bill_amount(self):
        if self.payment_model == "PER_STUDENT":
            return self.amount_per_student * self.student_count_snapshot

        return self.subscription_amount

    def grace_end_date(self):
        if not self.next_billing_date:
            return None
        return self.next_billing_date + timedelta(days=self.grace_period_days)

    def is_due(self):
        if not self.next_billing_date:
            return False
        return timezone.localdate() > self.next_billing_date and self.amount_due > 0

    def is_in_grace_period(self):
        grace_end = self.grace_end_date()

        if not self.next_billing_date or not grace_end:
            return False

        today = timezone.localdate()

        return (
            self.amount_due > 0
            and today > self.next_billing_date
            and today <= grace_end
        )

    def is_blocked(self):
        grace_end = self.grace_end_date()

        if self.status in ["BLOCKED", "SUSPENDED"]:
            return True

        if not grace_end:
            return False

        return self.amount_due > 0 and timezone.localdate() > grace_end

    def grace_days_remaining(self):
        grace_end = self.grace_end_date()

        if not grace_end:
            return 0

        remaining = (grace_end - timezone.localdate()).days
        return max(remaining, 0)

    def computed_status(self):
        if self.status == "SUSPENDED":
            return "SUSPENDED"

        if self.is_blocked():
            return "BLOCKED"

        if self.is_in_grace_period():
            return "GRACE"

        if self.is_due():
            return "DUE"

        return "ACTIVE"

    def mark_paid(self, amount):
        amount = Decimal(str(amount))

        self.amount_due = max(Decimal("0.00"), self.amount_due - amount)
        self.last_paid_date = timezone.localdate()

        if self.amount_due <= 0:
            self.status = "ACTIVE"
            self.critical_features_blocked = False

            if self.billing_cycle == "MONTHLY":
                self.next_billing_date = timezone.localdate() + timedelta(days=30)
            elif self.billing_cycle == "TERM":
                self.next_billing_date = timezone.localdate() + timedelta(days=90)
            elif self.billing_cycle == "YEARLY":
                self.next_billing_date = timezone.localdate() + timedelta(days=365)

        self.save()

    def __str__(self):
        return f"{self.school.name} - {self.plan_name}"

class SMSWalletTopUp(models.Model):
    STATUS_PENDING = "pending"
    STATUS_INITIATED = "initiated"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_INITIATED, "Initiated"),
        (STATUS_SUCCESS, "Successful"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="sms_wallet_topups",
    )

    tenant_schema = models.CharField(max_length=100)

    requested_by_name = models.CharField(max_length=150, blank=True)
    requested_by_email = models.EmailField(blank=True)

    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    account_reference = models.CharField(max_length=100, blank=True)

    merchant_request_id = models.CharField(max_length=150, blank=True)
    checkout_request_id = models.CharField(max_length=150, blank=True)

    mpesa_receipt_number = models.CharField(max_length=100, blank=True)
    result_code = models.CharField(max_length=20, blank=True)
    result_description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    wallet_credited = models.BooleanField(default=False)
    credited_at = models.DateTimeField(null=True, blank=True)

    raw_request_response = models.JSONField(default=dict, blank=True)
    raw_callback = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant_schema"]),
            models.Index(fields=["checkout_request_id"]),
            models.Index(fields=["mpesa_receipt_number"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.school.name} SMS top-up KES {self.amount} - {self.status}"
class Domain(DomainMixin):
    """Domain for each school tenant"""
    pass


class SuperAdminProfile(models.Model):
    """Super admin profile for managing all tenants"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="super_admin_profile"
    )
    is_super_admin = models.BooleanField(default=True)
    can_manage_all_tenants = models.BooleanField(default=True)
    can_view_all_data = models.BooleanField(default=True)
    can_manage_system_settings = models.BooleanField(default=True)
    phone_number = models.CharField(max_length=20, blank=True)
    backup_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Super Admin Profile"
        verbose_name_plural = "Super Admin Profiles"

    def __str__(self):
        return f"Super Admin: {self.user.username}"

    def get_full_name(self):
        return self.user.get_full_name() or self.user.username


@receiver(post_save, sender=User)
def create_superadmin_profile(sender, instance, created, **kwargs):
    """
    Auto-create SuperAdminProfile only for public-schema superusers.

    This must not run inside school tenant schemas, because tenant users
    such as admin/principal should not create SuperAdminProfile records.
    """
    current_schema = getattr(connection, "schema_name", "public")

    if current_schema != "public":
        return

    if instance.is_superuser:
        SuperAdminProfile.objects.get_or_create(user=instance)
