from django.contrib import admin

from .models import School, Domain, SchoolSubscriptionAccount


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "schema_name",
        "school_level",
        "is_active",
        "on_trial",
        "paid_until",
    )
    list_filter = (
        "school_level",
        "is_active",
        "on_trial",
    )
    search_fields = (
        "name",
        "schema_name",
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "tenant",
        "is_primary",
    )
    list_filter = (
        "is_primary",
    )
    search_fields = (
        "domain",
        "tenant__name",
        "tenant__schema_name",
    )


@admin.register(SchoolSubscriptionAccount)
class SchoolSubscriptionAccountAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "plan_name",
        "payment_model",
        "billing_cycle",
        "subscription_amount",
        "amount_per_student",
        "student_count_snapshot",
        "amount_due",
        "next_billing_date",
        "grace_period_days",
        "status",
        "critical_features_blocked",
        "updated_at",
    )

    list_filter = (
        "payment_model",
        "billing_cycle",
        "status",
        "critical_features_blocked",
    )

    search_fields = (
        "school__name",
        "school__schema_name",
        "plan_name",
        "account_reference",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "School",
            {
                "fields": (
                    "school",
                    "plan_name",
                    "account_reference",
                )
            },
        ),
        (
            "Payment Model",
            {
                "fields": (
                    "payment_model",
                    "billing_cycle",
                    "subscription_amount",
                    "amount_per_student",
                    "student_count_snapshot",
                    "auto_calculate_amount_due",
                )
            },
        ),
        (
            "Billing Status",
            {
                "fields": (
                    "amount_due",
                    "next_billing_date",
                    "last_paid_date",
                    "grace_period_days",
                    "status",
                    "critical_features_blocked",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                )
            },
        ),
        (
            "System Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
