from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Unified Super Admin Dashboard (NEW - Main entry point)
    path('super-admin/', views.unified_super_admin_dashboard, name='unified_super_admin_dashboard'),
    path('super-admin/dashboard/', views.unified_super_admin_dashboard, name='super_admin_dashboard'),
    
    # Legacy Super Admin Dashboard (keep for backward compatibility)
    path('super-admin/old-dashboard/', views.super_admin_dashboard, name='super_admin_dashboard_old'),
    
    # Tenant Management URLs
    path('secure-admin/dashboard/', views.tenant_dashboard, name='tenant_dashboard'),
    path('secure-admin/tenant/<int:tenant_id>/', views.tenant_detail, name='tenant_detail'),
    path('secure-admin/tenant/<int:tenant_id>/edit/', views.tenant_edit, name='tenant_edit'),
    path('secure-admin/tenant/<int:tenant_id>/delete/', views.tenant_delete, name='tenant_delete'),
    path('secure-admin/tenant/<int:tenant_id>/reset-password/', views.reset_tenant_password, name='reset_tenant_password'),
    
    # Domain Management URLs
    path('secure-admin/tenant/<int:tenant_id>/add-domain/', views.add_domain, name='add_domain'),
    path('secure-admin/domain/<int:domain_id>/remove/', views.remove_domain, name='remove_domain'),
    path('secure-admin/domain/<int:domain_id>/set-primary/', views.set_primary_domain, name='set_primary_domain'),
    
    # Tenant Creation URL
    path('secure-admin/basil-create-school-tenant-2026/', views.create_tenant, name='create_tenant'),
]