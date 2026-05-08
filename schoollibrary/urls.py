# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse
from functools import wraps
from django.db import connection


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def home_redirect(request):
    return redirect('/app/')


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant"""
    return redirect(f'/tenant/{tenant_schema}/app/')


# Wrapper to ignore the tenant_schema parameter for admin
def wrap_admin(view_func):
    @wraps(view_func)
    def wrapper(request, tenant_schema=None, **kwargs):
        # Force public schema for admin
        connection.set_schema('public')
        return view_func(request, **kwargs)
    return wrapper


# Wrapper to force public schema for login view
def public_schema_login(view_func):
    """Force the login view to run in the public schema"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Store original schema and switch to public
        original_schema = connection.schema_name
        connection.set_schema('public')
        try:
            response = view_func(request, *args, **kwargs)
        finally:
            # Switch back to original schema
            connection.set_schema(original_schema)
        return response
    return wrapper


urlpatterns = [
    # ========== HEALTH CHECKS ==========
    path('healthz/', health_check),
    path('health/', health_check),

    # ========== HOME ==========
    path('', home_redirect, name='home'),

    # ========== PUBLIC ADMIN (NO TENANT PARAMETER) ==========
    # This MUST come BEFORE tenant patterns
    path('admin/', admin.site.urls),

    # ========== AUTHENTICATION ==========
    path('accounts/', include('django.contrib.auth.urls')),
    path(
        'login/',
        public_schema_login(
            auth_views.LoginView.as_view(
                template_name='digitallibrary/login.html'
            )
        ),
        name='login'
    ),

    # ========== TENANT-SPECIFIC URLS ==========
    # Tenant home redirect
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    
    # Tenant app portal
    path(
        'tenant/<str:tenant_schema>/app/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary'
        )
    ),
    
    # Tenant admin (wrapped to ignore tenant_schema parameter)
    path(
        'tenant/<str:tenant_schema>/admin/',
        wrap_admin(admin.site.urls)
    ),
    
    # Tenant library alias
    path(
        'tenant/<str:tenant_schema>/library/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary_alias'
        )
    ),

    # ========== LEGACY APP ROUTES (backward compatibility) ==========
    # Main App (without tenant - uses default tenant)
    path(
        'app/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary'
        )
    ),

    # Alias URL
    path(
        'library/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary_alias'
        )
    ),

    # ========== PWA / OFFLINE SUPPORT ==========
    path(
        'offline/',
        TemplateView.as_view(template_name='offline.html'),
        name='offline'
    ),
    path(
        'manifest.json/',
        TemplateView.as_view(
            template_name='manifest.json',
            content_type='application/json'
        ),
        name='manifest'
    ),
]

# ALWAYS serve media files
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)

# ALWAYS serve static files
urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT
)