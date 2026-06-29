from datetime import date

from django import forms

from .models import (
    School,
    SCHOOL_LEVEL_CHOICES,
    SchoolSubscriptionAccount,
)


def add_months_safe(source_date, months):
    """
    Add calendar months safely.

    Examples:
        2026-06-30 + 12 months = 2027-06-30
        2026-01-31 + 1 month = 2026-02-28
    """
    if not source_date:
        return None

    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1

    days_in_month = [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]

    day = min(source_date.day, days_in_month[month - 1])

    return date(year, month, day)


class TenantCreationForm(forms.Form):
    school_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. Nyandago Secondary School",
            }
        ),
        label="School Name",
    )

    schema_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. nyandago",
            }
        ),
        label="Tenant Schema Name",
        help_text=(
            "Use a short name such as nyandago. Spaces and hyphens "
            "will be converted to underscores."
        ),
    )

    school_level = forms.ChoiceField(
        choices=SCHOOL_LEVEL_CHOICES,
        initial="CBC_LEGACY_SECONDARY",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
        label="School Level",
        help_text="Select the school structure for this tenant.",
    )

    principal_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "principal@example.com",
            }
        ),
        label="Principal Email",
    )

    administrator_email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "admin@example.com",
            }
        ),
        label="Administrator Email",
    )

    def clean_schema_name(self):
        schema_name = self.cleaned_data.get("schema_name", "")

        schema_name = (
            schema_name
            .lower()
            .strip()
            .replace(" ", "_")
            .replace("-", "_")
        )

        if not schema_name:
            raise forms.ValidationError("Schema name is required.")

        if schema_name[0].isdigit():
            raise forms.ValidationError(
                "Schema name cannot start with a number."
            )

        for character in schema_name:
            if not (
                character.islower()
                or character.isdigit()
                or character == "_"
            ):
                raise forms.ValidationError(
                    (
                        "Schema name can only contain lowercase letters, "
                        "numbers, and underscores."
                    )
                )

        reserved_names = {
            "public",
            "admin",
            "login",
            "logout",
            "static",
            "media",
            "tenant",
            "tenants",
            "superadmin",
            "super_admin",
            "super-admin",
            "secure_admin",
            "secure-admin",
            "app",
            "library",
            "mpesa",
            "billing",
            "www",
        }

        if schema_name in reserved_names:
            raise forms.ValidationError(
                (
                    f"'{schema_name}' is reserved and cannot be used "
                    "as a tenant schema."
                )
            )

        if School.objects.filter(schema_name=schema_name).exists():
            raise forms.ValidationError(
                f"A tenant with schema '{schema_name}' already exists."
            )

        return schema_name

    def clean_school_level(self):
        school_level = self.cleaned_data.get("school_level")

        if not school_level:
            return "CBC_LEGACY_SECONDARY"

        return school_level

    def clean(self):
        cleaned_data = super().clean()

        principal_email = cleaned_data.get("principal_email")
        administrator_email = cleaned_data.get("administrator_email")

        if (
            principal_email
            and administrator_email
            and principal_email.lower() == administrator_email.lower()
        ):
            raise forms.ValidationError(
                "Principal email and administrator email should be different."
            )

        return cleaned_data


class TenantUpdateForm(forms.ModelForm):
    class Meta:
        model = School
        fields = [
            "name",
            "address",
            "phone_number",
            "email",
            "school_level",
        ]

        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                }
            ),
            "phone_number": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "school_level": forms.Select(
                attrs={"class": "form-control"}
            ),
        }


class ResetPasswordForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
            }
        )
    )

    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password",
            }
        ),
        min_length=8,
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm password",
            }
        )
    )

    def clean(self):
        cleaned_data = super().clean()

        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if (
            new_password
            and confirm_password
            and new_password != confirm_password
        ):
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class SchoolSubscriptionAccountForm(forms.ModelForm):
    class Meta:
        model = SchoolSubscriptionAccount

        fields = [
            "plan_name",
            "payment_model",
            "billing_cycle",
            "subscription_amount",
            "amount_per_student",
            "student_count_snapshot",
            "amount_due",
            "subscription_start_date",
            "subscription_end_date",
            "next_billing_date",
            "last_paid_date",
            "grace_period_days",
            "status",
            "critical_features_blocked",
            "auto_calculate_amount_due",
            "account_reference",
            "notes",
        ]

        widgets = {
            "plan_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. ShuleHub Standard",
                }
            ),
            "payment_model": forms.Select(
                attrs={
                    "class": "form-control",
                    "data-billing-field": "payment-model",
                }
            ),
            "billing_cycle": forms.Select(
                attrs={
                    "class": "form-control",
                    "data-billing-field": "billing-cycle",
                }
            ),
            "subscription_amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "e.g. 30000",
                    "data-billing-field": "subscription-amount",
                }
            ),
            "amount_per_student": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "e.g. 50",
                    "data-billing-field": "amount-per-student",
                }
            ),
            "student_count_snapshot": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "e.g. 450",
                    "data-billing-field": "student-count",
                }
            ),
            "amount_due": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "e.g. 30000",
                    "data-billing-field": "amount-due",
                }
            ),
            "subscription_start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "data-billing-field": "start-date",
                },
                format="%Y-%m-%d",
            ),
            "subscription_end_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "data-billing-field": "end-date",
                },
                format="%Y-%m-%d",
            ),
            "next_billing_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "data-billing-field": "next-billing-date",
                },
                format="%Y-%m-%d",
            ),
            "last_paid_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
                format="%Y-%m-%d",
            ),
            "grace_period_days": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "e.g. 30",
                    "data-billing-field": "grace-days",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "account_reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. SUB-MIYUGA",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Internal billing notes for this school...",
                }
            ),
        }

        labels = {
            "plan_name": "Plan Name",
            "payment_model": "Payment Model",
            "billing_cycle": "Billing Cycle",
            "subscription_amount": "Fixed Subscription Amount",
            "amount_per_student": "Amount Per Student",
            "student_count_snapshot": "Student Count Snapshot",
            "amount_due": "Amount Due",
            "subscription_start_date": "Subscription Start Date",
            "subscription_end_date": "Subscription End Date",
            "next_billing_date": "Next Billing Date",
            "last_paid_date": "Last Paid Date",
            "grace_period_days": "Grace Period Days",
            "status": "Subscription Status",
            "critical_features_blocked": "Block Critical Features",
            "auto_calculate_amount_due": "Auto Calculate Amount Due",
            "account_reference": "Account Reference",
            "notes": "Notes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        date_fields = [
            "subscription_start_date",
            "subscription_end_date",
            "next_billing_date",
            "last_paid_date",
        ]

        for field_name in date_fields:
            self.fields[field_name].input_formats = ["%Y-%m-%d"]

    def calculate_end_date(self, start_date, billing_cycle):
        if not start_date:
            return None

        if billing_cycle == "MONTHLY":
            return add_months_safe(start_date, 1)

        if billing_cycle == "TERM":
            return add_months_safe(start_date, 3)

        if billing_cycle == "YEARLY":
            return add_months_safe(start_date, 12)

        return None

    def clean(self):
        cleaned_data = super().clean()

        billing_cycle = cleaned_data.get("billing_cycle")
        payment_model = cleaned_data.get("payment_model")
        subscription_amount = cleaned_data.get("subscription_amount")
        amount_per_student = cleaned_data.get("amount_per_student")
        student_count_snapshot = cleaned_data.get("student_count_snapshot") or 0
        grace_period_days = cleaned_data.get("grace_period_days")
        start_date = cleaned_data.get("subscription_start_date")

        if grace_period_days is None:
            cleaned_data["grace_period_days"] = 30

        calculated_end_date = self.calculate_end_date(
            start_date,
            billing_cycle,
        )

        if calculated_end_date:
            cleaned_data["subscription_end_date"] = calculated_end_date
            cleaned_data["next_billing_date"] = calculated_end_date

        end_date = cleaned_data.get("subscription_end_date")
        next_billing_date = cleaned_data.get("next_billing_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "Subscription end date cannot be earlier than the start date."
            )

        if start_date and next_billing_date and next_billing_date < start_date:
            raise forms.ValidationError(
                "Next billing date cannot be earlier than the subscription start date."
            )

        if subscription_amount is not None and subscription_amount < 0:
            raise forms.ValidationError(
                "Subscription amount cannot be negative."
            )

        if amount_per_student is not None and amount_per_student < 0:
            raise forms.ValidationError(
                "Amount per student cannot be negative."
            )

        if student_count_snapshot is not None and student_count_snapshot < 0:
            raise forms.ValidationError(
                "Student count cannot be negative."
            )

        if payment_model == "PER_STUDENT":
            if not amount_per_student or amount_per_student <= 0:
                raise forms.ValidationError(
                    "Enter amount per student when using Per Student billing."
                )

            if not student_count_snapshot or student_count_snapshot <= 0:
                raise forms.ValidationError(
                    "Enter student count when using Per Student billing."
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        calculated_end_date = self.calculate_end_date(
            instance.subscription_start_date,
            instance.billing_cycle,
        )

        if calculated_end_date:
            instance.subscription_end_date = calculated_end_date
            instance.next_billing_date = calculated_end_date

        if instance.grace_period_days is None:
            instance.grace_period_days = 30

        if instance.auto_calculate_amount_due:
            instance.amount_due = instance.expected_bill_amount()

        if instance.status == "ACTIVE" and instance.amount_due <= 0:
            instance.critical_features_blocked = False

        if instance.status in ["BLOCKED", "SUSPENDED"]:
            instance.critical_features_blocked = True

        if commit:
            instance.save()
            self.save_m2m()

        return instance
