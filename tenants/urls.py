from django.urls import path
from django.shortcuts import redirect

from . import views


app_name = "tenants"


urlpatterns = [
    # ============================================================
    # Super Admin Dashboard
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

    # Legacy Super Admin Dashboard
    path(
        "super-admin/old-dashboard/",
        views.super_admin_dashboard,
        name="super_admin_dashboard_old",
    ),

    # ============================================================
    # Clean Public Superadmin Tenant Creation URL
    # This is the URL your templates should use.
    # ============================================================
    path(
        "create/",
        views.create_tenant,
        name="create_tenant",
    ),

    # ============================================================
    # Old Create Tenant URL Redirect
    # Keep this so old buttons/links do not send you to login.
    # ============================================================
    path(
        "secure-admin/basil-create-school-tenant-2026/",
        lambda request: redirect("tenants:create_tenant"),
        name="basil_create_school_tenant_2026_redirect",
    ),

    # ============================================================
    # Tenant Management URLs
    # ============================================================
    path(
        "secure-admin/dashboard/",
        views.tenant_dashboard,
        name="tenant_dashboard",
    ),
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
