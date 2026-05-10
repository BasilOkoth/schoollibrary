# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse, Http404
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def home_redirect(request):
    """Redirect root to app for both public and tenant domains"""
    logger.info(f"Home redirect called. Host: {request.get_host()}, Path: {request.path}")
    return redirect('/app/')


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant"""
    return redirect(f'/tenant/{tenant_schema}/app/')


# Wrapper to ignore the tenant_schema parameter for admin
def wrap_admin(view_func):
    @wraps(view_func)
    def wrapper(request, tenant_schema=None, **kwargs):
        # Force public schema for admin
        from django.db import connection
        connection.set_schema('public')
        return view_func(request, **kwargs)
    return wrapper


# Debug view to check routing
def debug_routing(request):
    """Debug view to check what's happening with routing"""
    from django.db import connection
    import sys
    
    debug_info = f"""
    <h1>Debug Routing Info</h1>
    <p>Host: {request.get_host()}</p>
    <p>Path: {request.path}</p>
    <p>Method: {request.method}</p>
    <p>Current Schema: {connection.schema_name}</p>
    <p>Is Authenticated: {request.user.is_authenticated}</p>
    <p>Session Key: {request.session.session_key}</p>
    <p>Python Version: {sys.version}</p>
    """
    return HttpResponse(debug_info, content_type="text/html")


urlpatterns = [
    # ========== HEALTH CHECKS ==========
    path('healthz/', health_check),
    path('health/', health_check),
    
    # ========== DEBUG ROUTING (remove after fixing) ==========
    path('debug/', debug_routing, name='debug'),

    # ========== HOME ==========
    # Root path - redirect to /app/
    path('', home_redirect, name='home'),

    # ========== PUBLIC ADMIN (NO TENANT PARAMETER) ==========
    # This MUST come BEFORE tenant patterns
    path('admin/', admin.site.urls),

    # ========== AUTHENTICATION ==========
    path('accounts/login/', RedirectView.as_view(url='/login/', permanent=False), name='accounts_login'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='digitallibrary/login.html',
            redirect_authenticated_user=True
        ),
        name='login'
    ),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='accounts_logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='digitallibrary/password_reset.html',
        email_template_name='digitallibrary/password_reset_email.html',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='digitallibrary/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='digitallibrary/password_reset_confirm.html',
        success_url='/password-reset-complete/',
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='digitallibrary/password_reset_complete.html',
    ), name='password_reset_complete'),

    # ========== TENANT-SPECIFIC URLS ==========
    # Tenant home redirect
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    
    # Tenant app portal
    path(
        'tenant/<str:tenant_schema>/app/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='tenant_app'
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
            namespace='tenant_lib'
        )
    ),

    # ========== LEGACY APP ROUTES (backward compatibility) ==========
    # Main App (without tenant - uses public schema)
    # IMPORTANT: This handles /app/ on public domain (shulehub.org)
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

# ========== CATCH-ALL FOR DEBUGGING (remove in production) ==========
# This helps debug missing URLs
if settings.DEBUG:
    def catch_all(request, path):
        logger.warning(f"Catch-all triggered for path: {path} on host: {request.get_host()}")
        return HttpResponse(f"<h1>Page not found</h1><p>Path: {path}</p><p>Host: {request.get_host()}</p>", status=404)
    
    urlpatterns += [
        path('<path:path>', catch_all),
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
