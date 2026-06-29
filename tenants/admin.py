from django.contrib import admin
from .models import School, Domain

admin.site.register(School)
admin.site.register(Domain)
from django.contrib import admin
from .models import SchoolSubscriptionAccount, SchoolSubscriptionPayment


@admin.register(SchoolSubscriptionAccount)
class SchoolSubscriptionAccountAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "plan_name",
        "billing_cycle",
        "subscription_amount",
        "amount_due",
        "next_billing_date",
        "status",
        "critical_features_blocked",
    )
    list_filter = ("status", "billing_cycle", "critical_features_blocked")
    search_fields = ("school__name", "school__schema_name", "account_reference")


@admin.register(SchoolSubscriptionPayment)
class SchoolSubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "school",
        "tenant_schema",
        "amount",
        "phone_number",
        "mpesa_receipt_number",
        "status",
        "subscription_updated",
        "created_at",
    )
    list_filter = ("status", "subscription_updated", "created_at")
    search_fields = (
        "school__name",
        "tenant_schema",
        "phone_number",
        "mpesa_receipt_number",
        "checkout_request_id",
    )
