# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for Render"""
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
        from django.db import connection
        connection.set_schema('public')
        return view_func(request, **kwargs)
    return wrapper


urlpatterns = [
    # ========== HEALTH CHECKS ==========
    path('healthz/', health_check),
    path('health/', health_check),
    
    # ========== HOME ==========
    path('', home_redirect, name='home'),
    
    # ========== PUBLIC ADMIN (NO TENANT PARAMETER) ==========
    path('admin/', admin.site.urls),
    path('superadmin/', include('superadmin.urls')),
    
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
    
    # ========== PASSWORD RESET ==========
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
    
    # ========== M-PESA ==========
    path('mpesa/', include('mpesa.urls')),
    
    # ========== TENANT-SPECIFIC URLS ==========
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    path(
        'tenant/<str:tenant_schema>/app/',
        include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_app')
    ),
    path(
        'tenant/<str:tenant_schema>/admin/',
        wrap_admin(admin.site.urls)
    ),
    path(
        'tenant/<str:tenant_schema>/library/',
        include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_lib')
    ),
    
    # ========== LEGACY APP ROUTES (backward compatibility) ==========
    path(
        'app/',
        include(('digitallibrary.urls', 'digitallibrary'), namespace='digitallibrary')
    ),
    path(
        'library/',
        include(('digitallibrary.urls', 'digitallibrary'), namespace='digitallibrary_alias')
    ),
    path('tenants/', include('tenants.urls')),
    
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

# ========== STATIC AND MEDIA FILES ==========
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ========== CATCH-ALL FOR DEBUGGING (development only) ==========
if settings.DEBUG:
    def catch_all(request, path):
        logger.warning(f"Catch-all triggered for path: {path} on host: {request.get_host()}")
        return HttpResponse(f"<h1>Page not found</h1><p>Path: {path}</p><p>Host: {request.get_host()}</p>", status=404)
    
    urlpatterns += [
        path('<path:path>', catch_all),
    ]
