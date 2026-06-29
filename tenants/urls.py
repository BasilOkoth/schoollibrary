from django.urls import path
from django.shortcuts import redirect
from . import views


app_name = "tenants"


urlpatterns = [
    # ============================================================
    # Main Unified Super Admin Dashboard
    # This is the dashboard with the SMS Wallets card
    # ============================================================
    path(
        "super-admin/",
        views.unified_super_admin_dashboard,
        name="unified_super_admin_dashboard",
    ),
    path(
        "super-admin/dashboard/",
        views.unified_super_admin_dashboard,
        name="super_admin_dashboard",
    ),

    # ============================================================
    # SMS Wallet Dashboard
    # This opens the dashboard that has SMS Wallet Overview + Top-Up form
    # ============================================================
    path(
        "super-admin/old-dashboard/",
        views.super_admin_dashboard,
        name="super_admin_dashboard_old",
   
    path(
    "superadmin/billing/",
    views.superadmin_billing_list,
    name="superadmin_billing_list",
    ),
    path(
    "superadmin/billing/<int:school_id>/edit/",
    views.superadmin_billing_edit,
    name="superadmin_billing_edit",
),
    ),

    # ============================================================
    # SMS Wallet Top-Up
    # ============================================================
    path(
        "super-admin/sms-wallet/<int:school_id>/top-up/",
        views.top_up_school_sms_wallet,
        name="top_up_school_sms_wallet",
    ),

    # ============================================================
    # Clean Public Superadmin Tenant Creation URL
    # ============================================================
    path(
        "create/",
        views.create_tenant,
        name="create_tenant",
    ),
    path(
    "mpesa/callback/sms-wallet/",
    views.mpesa_sms_wallet_callback,
    name="mpesa_sms_wallet_callback",
    ),
    path(
    "mpesa/callback/subscription/",
    views.mpesa_subscription_callback,
    name="mpesa_subscription_callback",
    ),
    # ============================================================
    # Old / Legacy URLs Redirected Safely
    # ============================================================
    path(
        "secure-admin/dashboard/",
        lambda request: redirect("tenants:unified_super_admin_dashboard"),
        name="tenant_dashboard",
    ),
    path(
        "secure-admin/basil-create-school-tenant-2026/",
        lambda request: redirect("tenants:create_tenant"),
        name="basil_create_school_tenant_2026_redirect",
    ),

    # ============================================================
    # Tenant Management URLs
    # ============================================================
    path(
        "secure-admin/tenant/<int:tenant_id>/",
        views.tenant_detail,
        name="tenant_detail",
    ),
    path(
        "secure-admin/tenant/<int:tenant_id>/edit/",
        views.tenant_edit,
        name="tenant_edit",
    ),
    path(
        "secure-admin/tenant/<int:tenant_id>/delete/",
        views.tenant_delete,
        name="tenant_delete",
    ),
    path(
        "secure-admin/tenant/<int:tenant_id>/reset-password/",
        views.reset_tenant_password,
        name="reset_tenant_password",
    ),
    path(
        "secure-admin/tenant/<int:tenant_id>/fix-migrations/",
        views.fix_tenant_migrations,
        name="fix_tenant_migrations",
    ),

    # ============================================================
    # Domain Management URLs
    # ============================================================
    path(
        "secure-admin/tenant/<int:tenant_id>/add-domain/",
        views.add_domain,
        name="add_domain",
    ),
    path(
        "secure-admin/domain/<int:domain_id>/remove/",
        views.remove_domain,
        name="remove_domain",
    ),
    path(
        "secure-admin/domain/<int:domain_id>/set-primary/",
        views.set_primary_domain,
        name="set_primary_domain",
    ),
]
