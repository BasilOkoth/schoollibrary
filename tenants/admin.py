from django.contrib import admin

from .models import (
    School,
    Domain,
    SchoolSubscriptionAccount,
    SchoolSubscriptionPayment,
)


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
        "subscription_start_date",
        "subscription_end_date",
        "next_billing_date",
        "last_paid_date",
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
        "subscription_start_date",
        "subscription_end_date",
        "next_billing_date",
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
            "Subscription Period",
            {
                "fields": (
                    "subscription_start_date",
                    "subscription_end_date",
                    "next_billing_date",
                    "last_paid_date",
                )
            },
        ),
        (
            "Billing Status",
            {
                "fields": (
                    "amount_due",
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


@admin.register(SchoolSubscriptionPayment)
class SchoolSubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "tenant_schema",
        "amount",
        "phone_number",
        "status",
        "mpesa_receipt_number",
        "checkout_request_id",
        "subscription_updated",
        "created_at",
    )

    list_filter = (
        "status",
        "subscription_updated",
        "created_at",
        "tenant_schema",
    )

    search_fields = (
        "school__name",
        "school__schema_name",
        "tenant_schema",
        "phone_number",
        "mpesa_receipt_number",
        "checkout_request_id",
        "merchant_request_id",
        "requested_by_name",
        "requested_by_email",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "raw_request_response",
        "raw_callback",
        "updated_subscription_at",
    )

    fieldsets = (
        (
            "School",
            {
                "fields": (
                    "school",
                    "tenant_schema",
                    "account_reference",
                )
            },
        ),
        (
            "Payment Details",
            {
                "fields": (
                    "amount",
                    "phone_number",
                    "status",
                    "mpesa_receipt_number",
                    "result_code",
                    "result_description",
                )
            },
        ),
        (
            "Requested By",
            {
                "fields": (
                    "requested_by_name",
                    "requested_by_email",
                )
            },
        ),
        (
            "M-Pesa Tracking",
            {
                "fields": (
                    "merchant_request_id",
                    "checkout_request_id",
                    "raw_request_response",
                    "raw_callback",
                )
            },
        ),
        (
            "Subscription Update",
            {
                "fields": (
                    "subscription_updated",
                    "updated_subscription_at",
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
