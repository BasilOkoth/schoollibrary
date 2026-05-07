# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant"""
    return redirect(f'/tenant/{tenant_schema}/app/')


urlpatterns = [
    # Health checks
    path('healthz/', health_check),
    path('health/', health_check),

    # Redirect homepage to app dashboard
    path('', lambda req: redirect('/app/')),

    # Public schema admin (for managing tenants)
    path('admin/', admin.site.urls),

    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),

    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='digitallibrary/login.html'
        ),
        name='login'
    ),

    # ============================================================
    # TENANT-SPECIFIC URLs (MULTI-TENANCY)
    # ============================================================
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
    
    # IMPORTANT: Tenant admin access - allows each school to have its own admin panel
    path(
        'tenant/<str:tenant_schema>/admin/',
        admin.site.urls
    ),
    
    # Tenant library alias
    path(
        'tenant/<str:tenant_schema>/library/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary_alias'
        )
    ),

    # ============================================================
    # LEGACY ROUTES (for backward compatibility)
    # ============================================================
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

    # ============================================================
    # PWA / OFFLINE SUPPORT
    # ============================================================
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